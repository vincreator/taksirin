"""
vision_service.py
─────────────────
Menggunakan Google Gemini (GRATIS) untuk menganalisis foto barang
dan menghasilkan informasi identifikasi serta kata kunci pencarian.

API Key gratis di: https://aistudio.google.com/app/apikey
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Optional

from google import genai
from google.genai.errors import ClientError
from google.genai import types
from PIL import Image

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger(__name__)

# Client Gemini (SDK baru)
_client = genai.Client(api_key=GEMINI_API_KEY)
_VISION_LOCAL_BLOCK_UNTIL: float = 0.0


def _extract_retry_seconds(error_text: str, default_seconds: int = 60) -> int:
    text = error_text or ""
    patterns = [
        r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
        r"retryDelay'?:\s*'([0-9]+)s'",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            try:
                return max(5, int(float(match.group(1))))
            except Exception:
                pass
    return default_seconds


def _is_quota_or_rate_limit(error_text: str) -> bool:
    err = (error_text or "").lower()
    return (
        "resource_exhausted" in err
        or "quota exceeded" in err
        or "rate limit" in err
        or "429" in err
    )


def _normalize_model_name(model_name: str) -> str:
    """Pastikan format model name sesuai SDK baru (models/...)."""
    model_name = (model_name or "").strip()
    if not model_name:
        return "models/gemini-2.0-flash"
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


def _model_candidates() -> list[str]:
    """Urutan model fallback jika model utama tidak tersedia."""
    candidates = [
        _normalize_model_name(GEMINI_MODEL),
        "models/gemini-2.0-flash",
        "models/gemini-2.0-flash-lite",
        "models/gemini-flash-latest",
        "models/gemini-2.5-flash",
    ]
    # unique, preserve order
    return list(dict.fromkeys(candidates))


@dataclass
class ItemAnalysis:
    """Hasil analisis foto barang."""
    item_name: str                          # Nama barang (contoh: "Laptop ASUS VivoBook 14")
    brand: str                              # Merek (contoh: "ASUS")
    category: str                           # Kategori (contoh: "Elektronik")
    condition_guess: str                    # Perkiraan kondisi: "Baru", "Bekas - Bagus", dsb.
    description: str                        # Deskripsi singkat barang
    search_keywords: list[str] = field(default_factory=list)   # Kata kunci pencarian
    estimated_price_min: Optional[int] = None   # Estimasi harga minimum (Rp)
    estimated_price_max: Optional[int] = None   # Estimasi harga maksimum (Rp)
    confidence: str = "medium"              # Tingkat keyakinan: low / medium / high
    error: Optional[str] = None            # Pesan error jika gagal


ANALYSIS_PROMPT = """Kamu adalah asisten penilai harga barang bekas / baru di Indonesia.
Analisis foto barang yang dikirim user dan berikan respons dalam format JSON persis seperti ini:

{
  "item_name": "Nama lengkap barang (merek + model jika terlihat)",
  "brand": "Merek barang (atau 'Tidak diketahui')",
  "category": "Kategori barang (contoh: Elektronik, Furnitur, Pakaian, Kendaraan, dll.)",
  "condition_guess": "Perkiraan kondisi: Baru / Bekas - Baik / Bekas - Cukup / Bekas - Rusak",
  "description": "Deskripsi singkat 1-2 kalimat tentang barang ini",
  "search_keywords": ["keyword1", "keyword2", "keyword3"],
  "estimated_price_min": 100000,
  "estimated_price_max": 500000,
  "confidence": "low/medium/high"
}

Aturan:
- `search_keywords`: 3-5 kata kunci relevan untuk dicari di Tokopedia & OLX (dalam Bahasa Indonesia)
- `estimated_price_min` & `estimated_price_max`: perkiraan harga dalam Rupiah berdasarkan pengetahuanmu tentang pasar Indonesia
- `confidence`: seberapa yakin kamu mengidentifikasi barang ini
- Jika foto tidak jelas atau bukan foto barang, set `item_name` = "TIDAK_TERIDENTIFIKASI"
- Hanya balas dengan JSON, tanpa teks tambahan apapun"""


async def analyze_image(image_bytes: bytes) -> ItemAnalysis:
    """
    Analisis gambar menggunakan Google Gemini Vision (GRATIS).

    Args:
        image_bytes: Byte data gambar (JPEG/PNG/WebP)

    Returns:
        ItemAnalysis dataclass berisi hasil analisis
    """
    global _VISION_LOCAL_BLOCK_UNTIL

    # Circuit breaker lokal agar tidak spam request saat quota sedang habis
    now = time.monotonic()
    if _VISION_LOCAL_BLOCK_UNTIL > now:
        remaining = int(_VISION_LOCAL_BLOCK_UNTIL - now)
        return ItemAnalysis(
            item_name="Error",
            brand="",
            category="",
            condition_guess="",
            description="",
            error=f"429 RESOURCE_EXHAUSTED. Retry in {remaining}s",
        )

    try:
        # Buka gambar menggunakan Pillow
        pil_image = Image.open(io.BytesIO(image_bytes))

        # Pastikan format RGB (Gemini tidak support RGBA/P mode)
        if pil_image.mode not in ("RGB", "L"):
            pil_image = pil_image.convert("RGB")

        # Kirim gambar + prompt ke Gemini (async) dengan fallback model
        last_exc: Exception | None = None
        raw_text = ""
        selected_model = ""

        for model_name in _model_candidates():
            try:
                response = await _client.aio.models.generate_content(
                    model=model_name,
                    contents=[ANALYSIS_PROMPT, pil_image],
                    config=types.GenerateContentConfig(
                        temperature=0.2,
                        max_output_tokens=800,
                    ),
                )
                raw_text = response.text or ""
                selected_model = model_name
                break
            except ClientError as exc:
                last_exc = exc
                err = str(exc).lower()
                if _is_quota_or_rate_limit(err):
                    wait_seconds = _extract_retry_seconds(str(exc))
                    _VISION_LOCAL_BLOCK_UNTIL = time.monotonic() + wait_seconds
                    logger.warning(
                        "Gemini quota/rate-limit aktif. Cooldown %ss.",
                        wait_seconds,
                    )
                    break
                if "not_found" in err or "not found" in err or "is not supported" in err:
                    logger.warning("Model '%s' tidak tersedia, coba fallback berikutnya", model_name)
                    continue
                raise
            except Exception as exc:
                last_exc = exc
                raise

        if not raw_text:
            if last_exc:
                raise last_exc
            raise RuntimeError("Gemini tidak mengembalikan respons teks")

        logger.info("Gemini model: %s | raw response: %s", selected_model, raw_text[:300])

        # Bersihkan code block markdown jika ada
        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else raw_text
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        data = json.loads(raw_text.strip())

        return ItemAnalysis(
            item_name=data.get("item_name", "Tidak diketahui"),
            brand=data.get("brand", "Tidak diketahui"),
            category=data.get("category", "Lainnya"),
            condition_guess=data.get("condition_guess", "Tidak diketahui"),
            description=data.get("description", ""),
            search_keywords=data.get("search_keywords", []),
            estimated_price_min=data.get("estimated_price_min"),
            estimated_price_max=data.get("estimated_price_max"),
            confidence=data.get("confidence", "medium"),
        )

    except ClientError as exc:
        err_text = str(exc)
        if _is_quota_or_rate_limit(err_text):
            wait_seconds = _extract_retry_seconds(err_text)
            _VISION_LOCAL_BLOCK_UNTIL = time.monotonic() + wait_seconds
            logger.warning("Gemini quota/rate-limit. Cooldown %ss.", wait_seconds)
        else:
            logger.warning("Gemini ClientError: %s", err_text[:300])
        return ItemAnalysis(
            item_name="Error",
            brand="",
            category="",
            condition_guess="",
            description="",
            error=err_text,
        )
    except Exception as exc:
        logger.warning("Error saat menganalisis gambar: %s", str(exc)[:300])
        return ItemAnalysis(
            item_name="Error",
            brand="",
            category="",
            condition_guess="",
            description="",
            error=str(exc),
        )
