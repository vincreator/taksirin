"""
tokopedia_service.py
────────────────────
Mencari harga barang di Tokopedia menggunakan API internal mereka.
Endpoint: https://ace.tokopedia.com/search/v4.6/product
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Optional

import httpx

from config import DEFAULT_HEADERS, MAX_RESULTS_PER_SOURCE

logger = logging.getLogger(__name__)

TOKOPEDIA_SEARCH_URL = "https://ace.tokopedia.com/search/v4.6/product"

HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.tokopedia.com",
    "Referer": "https://www.tokopedia.com/",
    "X-Version": "1",
    "X-Source": "tokopedia-lite",
}

TOKOPEDIA_BLOCK_UNTIL: float = 0.0


@dataclass
class TokopediaProduct:
    name: str
    price: int           # dalam Rupiah
    price_text: str      # contoh: "Rp 150.000"
    shop_name: str
    url: str
    image_url: str
    rating: Optional[float] = None
    sold_count: Optional[int] = None
    location: str = ""


async def search_tokopedia(query: str) -> list[TokopediaProduct]:
    """
    Cari produk di Tokopedia berdasarkan kata kunci.

    Args:
        query: Kata kunci pencarian

    Returns:
        List TokopediaProduct
    """
    global TOKOPEDIA_BLOCK_UNTIL

    now = time.monotonic()
    if TOKOPEDIA_BLOCK_UNTIL > now:
        remaining = int(TOKOPEDIA_BLOCK_UNTIL - now)
        logger.info("Tokopedia sementara di-skip %ss lagi (circuit breaker aktif)", remaining)
        return []

    params = {
        "q": query,
        "start": 0,
        "rows": MAX_RESULTS_PER_SOURCE,
        "device": "desktop",
        "source": "search",
        "ob": "5",          # Sort by: 5 = paling relevan
        "st": "product",
    }

    try:
        data = await _request_tokopedia_json(params=params, query=query)
        if not data:
            return []

        products = []
        items = (
            data.get("data", {}).get("products", [])
            or data.get("products", [])
            or []
        )

        for item in items[:MAX_RESULTS_PER_SOURCE]:
            try:
                price_data = item.get("price", {})
                price_int = _parse_price(price_data)
                price_text = price_data.get("text_idr", "") or f"Rp {price_int:,}"

                shop = item.get("shop", {})
                rating_data = item.get("rating", {})

                products.append(
                    TokopediaProduct(
                        name=item.get("name", ""),
                        price=price_int,
                        price_text=price_text,
                        shop_name=shop.get("name", ""),
                        url=item.get("url", ""),
                        image_url=item.get("image_url", ""),
                        rating=float(rating_data.get("rate", 0) or 0) or None,
                        sold_count=item.get("count_review") or None,
                        location=shop.get("city", ""),
                    )
                )
            except Exception as exc:
                logger.warning("Skip item Tokopedia karena error: %s", exc)
                continue

        logger.info("Tokopedia: %d produk ditemukan untuk '%s'", len(products), query)
        return products

    except httpx.HTTPStatusError as exc:
        logger.warning("Tokopedia HTTP error %s untuk query '%s'", exc.response.status_code, query)
        return []
    except Exception as exc:
        logger.warning("Tokopedia error untuk query '%s': %r", query, exc)
        return []


async def _request_tokopedia_json(params: dict, query: str) -> dict:
    """Request ke endpoint Tokopedia dengan retry ringan untuk error 5xx/network."""
    global TOKOPEDIA_BLOCK_UNTIL
    max_attempts = 3

    for attempt in range(1, max_attempts + 1):
        try:
            async with httpx.AsyncClient(
                headers=HEADERS,
                timeout=15.0,
                follow_redirects=True,
                trust_env=False,
            ) as client:
                resp = await client.get(TOKOPEDIA_SEARCH_URL, params=params)

            if resp.status_code >= 500:
                if attempt < max_attempts:
                    await asyncio.sleep(0.8 * attempt)
                    continue
                TOKOPEDIA_BLOCK_UNTIL = time.monotonic() + 120
                logger.warning(
                    "Tokopedia 5xx setelah %d percobaan untuk query '%s' (status=%s). Pause 120s.",
                    max_attempts,
                    query,
                    resp.status_code,
                )
                return {}

            resp.raise_for_status()
            return resp.json()

        except (httpx.TimeoutException, httpx.RequestError) as exc:
            if attempt < max_attempts:
                await asyncio.sleep(0.8 * attempt)
                continue
            logger.warning(
                "Tokopedia request gagal setelah %d percobaan untuk query '%s': %r",
                max_attempts,
                query,
                exc,
            )
            return {}

    return {}


def _parse_price(price_data: dict | str | int | None) -> int:
    """Konversi berbagai format harga ke integer (Rupiah)."""
    if isinstance(price_data, int):
        return price_data
    if isinstance(price_data, dict):
        # Coba beberapa field
        for key in ("value", "value_per_item", "min_price"):
            val = price_data.get(key)
            if val:
                return int(val)
        # Parse dari text seperti "Rp150.000"
        text = price_data.get("text_idr", "") or price_data.get("text", "")
        return _price_from_text(text)
    if isinstance(price_data, str):
        return _price_from_text(price_data)
    return 0


def _price_from_text(text: str) -> int:
    """Ekstrak angka dari string harga seperti 'Rp 150.000'."""
    import re
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0
