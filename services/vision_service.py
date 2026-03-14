"""
vision_service.py
─────────────────
Menggunakan provider AI text-only untuk memahami query user
dan menghasilkan estimasi harga yang lebih rapi.
"""

from __future__ import annotations

import json
import logging
import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Optional

from config import (
    AI_PROVIDER,
    AI_PROVIDER_LABEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    GROQ_API_KEY,
    GROQ_MODEL,
)

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import ClientError as GeminiClientError
except ImportError:
    genai = None
    types = None
    GeminiClientError = Exception

try:
    from groq import APIError as GroqAPIError
    from groq import AsyncGroq
except ImportError:
    GroqAPIError = Exception
    AsyncGroq = None

logger = logging.getLogger(__name__)

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if genai and GEMINI_API_KEY else None
_groq_client = AsyncGroq(api_key=GROQ_API_KEY) if AsyncGroq and GROQ_API_KEY else None
_TEXT_LOCAL_BLOCK_UNTIL: float = 0.0
_RECENT_ANALYSIS_CACHE: dict[str, tuple[float, "ItemAnalysis"]] = {}
_CACHE_TTL_SECONDS = 120.0

USED_CONDITION = "Bekas"
NEW_CONDITION = "Baru"


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
        or "too many requests" in err
        or "429" in err
    )


def _normalize_gemini_model_name(model_name: str) -> str:
    model_name = (model_name or "").strip()
    if not model_name:
        return "models/gemini-2.0-flash-lite"
    if model_name.startswith("models/"):
        return model_name
    return f"models/{model_name}"


def _gemini_model_candidates() -> list[str]:
    candidates = [
        _normalize_gemini_model_name(GEMINI_MODEL),
        "models/gemini-2.0-flash-lite",
        "models/gemini-2.0-flash",
        "models/gemini-flash-latest",
    ]
    return list(dict.fromkeys(candidates))


def _groq_model_candidates() -> list[str]:
    candidates = [
        (GROQ_MODEL or "").strip(),
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
    ]
    return [candidate for candidate in dict.fromkeys(candidates) if candidate]


@dataclass
class ItemAnalysis:
    item_name: str
    brand: str
    category: str
    condition_guess: str
    description: str
    search_keywords: list[str] = field(default_factory=list)
    estimated_price_min: Optional[int] = None
    estimated_price_max: Optional[int] = None
    confidence: str = "medium"
    error: Optional[str] = None


TEXT_ANALYSIS_PROMPT = """Kamu adalah asisten penilai harga barang di Indonesia.
User hanya mengirim teks nama barang. Tugasmu adalah memahami barang itu dan memberi taksiran harga singkat yang masuk akal.

Balas dalam format JSON persis seperti ini:

{
  "item_name": "Nama barang yang sudah dirapikan",
  "brand": "Merek barang (atau 'Tidak diketahui')",
  "category": "Kategori barang (contoh: Elektronik, Furnitur, Pakaian, Kendaraan, dll.)",
  "condition_guess": "Tidak diketahui kecuali jelas dari teks",
  "description": "Deskripsi singkat 1 kalimat dari barang yang dimaksud user",
  "search_keywords": ["keyword1", "keyword2", "keyword3"],
  "estimated_price_min": 100000,
  "estimated_price_max": 500000,
  "confidence": "low/medium/high"
}

Aturan:
- `search_keywords`: 3-5 kata kunci relevan yang bisa dipakai user untuk pencarian lanjutan
- Perbaiki typo ringan jika sangat jelas. Contoh: `egel` bisa jadi `eiger`
- Jangan mengarang model yang tidak ada di teks kecuali koreksi typo sangat yakin
- `estimated_price_min` & `estimated_price_max`: boleh diisi jika yakin, jika tidak isi null
- `confidence`: seberapa yakin kamu memahami maksud query user
- Jika query menyebut `bekas`, `second`, `secound`, `second hand`, `seken`, `used`, `preloved`, atau `2nd`, WAJIB gunakan acuan harga barang bekas dan `condition_guess` harus menunjukkan bekas
- Jika query menyebut `baru`, `new`, `brand new`, atau `segel`, WAJIB gunakan acuan harga barang baru dan `condition_guess` harus menunjukkan baru
- Jangan pakai harga barang baru kalau user sudah jelas meminta harga bekas
- Jawaban harus singkat dan hemat token
- Hanya balas dengan JSON, tanpa teks tambahan apapun"""


def _detect_condition_hint(query: str) -> str | None:
    normalized = f" {re.sub(r'\s+', ' ', (query or '').strip().lower())} "

    used_patterns = [
        r"\bbekas\b",
        r"\bseken\b",
        r"\bsecond\b",
        r"\bsecound\b",
        r"\bsecend\b",
        r"\bsecond hand\b",
        r"\bsecondhand\b",
        r"\b2nd\b",
        r"\bused\b",
        r"\bpreloved\b",
    ]
    new_patterns = [
        r"\bbaru\b",
        r"\bnew\b",
        r"\bbrand new\b",
        r"\bsegel\b",
    ]

    if any(re.search(pattern, normalized) for pattern in used_patterns):
        return USED_CONDITION
    if any(re.search(pattern, normalized) for pattern in new_patterns):
        return NEW_CONDITION
    return None


def _build_analysis_prompt(condition_hint: str | None) -> str:
    if condition_hint == USED_CONDITION:
        return (
            TEXT_ANALYSIS_PROMPT
            + "\n\nInstruksi tambahan penting: user secara eksplisit meminta harga BEKAS/SECOND, jadi semua estimasi harga harus untuk pasar barang bekas."
        )
    if condition_hint == NEW_CONDITION:
        return (
            TEXT_ANALYSIS_PROMPT
            + "\n\nInstruksi tambahan penting: user secara eksplisit meminta harga BARU, jadi semua estimasi harga harus untuk barang baru."
        )
    return TEXT_ANALYSIS_PROMPT


def _apply_condition_hint(condition_guess: str, condition_hint: str | None) -> str:
    normalized = (condition_guess or "").strip()
    normalized_lower = normalized.lower()
    if condition_hint == USED_CONDITION:
        if not normalized or normalized == "Tidak diketahui":
            return USED_CONDITION
        if "bekas" in normalized_lower or "second" in normalized_lower or "seken" in normalized_lower:
            return normalized
        return f"{USED_CONDITION} - {normalized}"
    if condition_hint == NEW_CONDITION:
        if not normalized or normalized == "Tidak diketahui":
            return NEW_CONDITION
        if "baru" in normalized_lower or "new" in normalized_lower or "segel" in normalized_lower:
            return normalized
        return f"{NEW_CONDITION} - {normalized}"
    return normalized or "Tidak diketahui"


def _merge_search_keywords(base_keywords: list[str], query: str, condition_hint: str | None) -> list[str]:
    keywords = list(base_keywords or [])
    query_lower = (query or "").lower()
    if query:
        keywords.append(query)
    if condition_hint == USED_CONDITION:
        if query and "bekas" not in query_lower:
            keywords.append(f"{query} bekas")
        if (
            query
            and "second" not in query_lower
            and "secound" not in query_lower
            and "secend" not in query_lower
            and "second hand" not in query_lower
            and "2nd" not in query_lower
        ):
            keywords.append(f"{query} second")
    elif condition_hint == NEW_CONDITION:
        if query and "baru" not in query_lower and "new" not in query_lower:
            keywords.append(f"{query} baru")

    return list(dict.fromkeys([keyword.strip() for keyword in keywords if keyword and keyword.strip()]))[:5]


def _get_cached_analysis(query: str) -> ItemAnalysis | None:
    cached = _RECENT_ANALYSIS_CACHE.get(query)
    if not cached:
        return None
    cached_at, result = cached
    if time.monotonic() - cached_at > _CACHE_TTL_SECONDS:
        _RECENT_ANALYSIS_CACHE.pop(query, None)
        return None
    return deepcopy(result)


def _set_cached_analysis(query: str, result: ItemAnalysis) -> None:
    if not query:
        return
    _RECENT_ANALYSIS_CACHE[query] = (time.monotonic(), deepcopy(result))


async def analyze_text(query: str) -> ItemAnalysis:
    global _TEXT_LOCAL_BLOCK_UNTIL

    query = (query or "").strip()
    if not query:
        return _manual_analysis("")

    condition_hint = _detect_condition_hint(query)

    cached = _get_cached_analysis(query)
    if cached:
        return cached

    now = time.monotonic()
    if _TEXT_LOCAL_BLOCK_UNTIL > now:
        remaining = max(1, int(_TEXT_LOCAL_BLOCK_UNTIL - now))
        result = _manual_analysis(
            query,
            error=f"{AI_PROVIDER_LABEL} sedang rate limit, coba lagi sekitar {remaining} detik.",
        )
        _set_cached_analysis(query, result)
        return result

    try:
        raw_text, selected_model = await _generate_response_text(query, condition_hint)

        if not raw_text:
            result = _manual_analysis(query)
            _set_cached_analysis(query, result)
            return result

        logger.info("%s model: %s | raw response: %s", AI_PROVIDER_LABEL, selected_model, raw_text[:300])

        raw_text = raw_text.strip()
        if raw_text.startswith("```"):
            parts = raw_text.split("```")
            raw_text = parts[1] if len(parts) > 1 else raw_text
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        data = json.loads(raw_text.strip())

        result = ItemAnalysis(
            item_name=data.get("item_name", query) or query,
            brand=data.get("brand", "Tidak diketahui"),
            category=data.get("category", "Lainnya"),
            condition_guess=_apply_condition_hint(
                data.get("condition_guess", "Tidak diketahui"),
                condition_hint,
            ),
            description=data.get("description", f"Analisis berbasis query: {query}"),
            search_keywords=_merge_search_keywords(
                data.get("search_keywords", [query]) or [query],
                query,
                condition_hint,
            ),
            estimated_price_min=data.get("estimated_price_min"),
            estimated_price_max=data.get("estimated_price_max"),
            confidence=data.get("confidence", "medium"),
        )
        _set_cached_analysis(query, result)
        return result

    except (GeminiClientError, GroqAPIError) as exc:
        err_text = str(exc)
        if _is_quota_or_rate_limit(err_text):
            wait_seconds = _extract_retry_seconds(err_text)
            _TEXT_LOCAL_BLOCK_UNTIL = time.monotonic() + wait_seconds
            logger.warning("%s quota/rate-limit. Fallback manual %ss.", AI_PROVIDER_LABEL, wait_seconds)
            err_text = f"{AI_PROVIDER_LABEL} kena quota/rate limit, coba lagi sekitar {wait_seconds} detik."
        else:
            logger.warning("%s API error: %s", AI_PROVIDER_LABEL, err_text[:300])
        result = _manual_analysis(query, error=err_text)
        _set_cached_analysis(query, result)
        return result
    except Exception as exc:
        logger.warning("Error saat menganalisis query teks: %s", str(exc)[:300])
        result = _manual_analysis(query, error=str(exc))
        _set_cached_analysis(query, result)
        return result


async def _generate_response_text(query: str, condition_hint: str | None) -> tuple[str, str]:
    if AI_PROVIDER == "groq":
        return await _generate_with_groq(query, condition_hint)
    return await _generate_with_gemini(query, condition_hint)


async def _generate_with_gemini(query: str, condition_hint: str | None) -> tuple[str, str]:
    if not _gemini_client or not types:
        raise RuntimeError("Gemini client belum tersedia. Pastikan dependency terpasang.")

    last_exc: Exception | None = None
    prompt = _build_analysis_prompt(condition_hint)
    for model_name in _gemini_model_candidates():
        try:
            response = await _gemini_client.aio.models.generate_content(
                model=model_name,
                contents=[prompt, f"Query user: {query}"],
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=220,
                ),
            )
            return response.text or "", model_name
        except GeminiClientError as exc:
            last_exc = exc
            err = str(exc).lower()
            if _is_quota_or_rate_limit(err):
                raise
            if "not_found" in err or "not found" in err or "is not supported" in err:
                logger.warning("Model '%s' tidak tersedia, coba fallback berikutnya", model_name)
                continue
            raise

    if last_exc:
        raise last_exc
    return "", ""


async def _generate_with_groq(query: str, condition_hint: str | None) -> tuple[str, str]:
    if not _groq_client:
        raise RuntimeError("Groq client belum tersedia. Pastikan GROQ_API_KEY dan dependency sudah ada.")

    last_exc: Exception | None = None
    prompt = _build_analysis_prompt(condition_hint)
    for model_name in _groq_model_candidates():
        try:
            response = await _groq_client.chat.completions.create(
                model=model_name,
                temperature=0.2,
                max_tokens=220,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Query user: {query}"},
                ],
            )
            content = response.choices[0].message.content if response.choices else ""
            return content or "", model_name
        except GroqAPIError as exc:
            last_exc = exc
            err = str(exc).lower()
            if _is_quota_or_rate_limit(err):
                raise
            if "model" in err and ("not found" in err or "does not exist" in err or "decommissioned" in err):
                logger.warning("Model Groq '%s' tidak tersedia, coba fallback berikutnya", model_name)
                continue
            raise

    if last_exc:
        raise last_exc
    return "", ""


def _manual_analysis(query: str, error: str | None = None) -> ItemAnalysis:
    cleaned = (query or "").strip()
    condition_hint = _detect_condition_hint(cleaned)
    keywords = [cleaned] if cleaned else []
    tokens = re.findall(r"[a-zA-Z0-9]+", cleaned)
    if len(tokens) >= 2:
        keywords.append(" ".join(tokens[:2]))
    if len(tokens) >= 3:
        keywords.append(" ".join(tokens[-2:]))

    deduped_keywords = _merge_search_keywords(keywords, cleaned, condition_hint)

    return ItemAnalysis(
        item_name=cleaned or "Tidak diketahui",
        brand="Manual",
        category="Tidak diketahui",
        condition_guess=condition_hint or "Tidak diketahui",
        description=f"Analisis berbasis teks: {cleaned}" if cleaned else "",
        search_keywords=deduped_keywords,
        estimated_price_min=None,
        estimated_price_max=None,
        confidence="medium",
        error=error,
    )
