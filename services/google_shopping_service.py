"""
google_shopping_service.py
──────────────────────────
Lookup harga online Google Shopping via SerpAPI.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import httpx

from config import (
    GOOGLE_SHOPPING_GL,
    GOOGLE_SHOPPING_HL,
    GOOGLE_SHOPPING_NUM,
    SERPAPI_KEY,
)


@dataclass
class ShoppingItem:
    title: str
    store: str
    price: int | None
    price_text: str
    link: str


@dataclass
class ShoppingSummary:
    query_used: str
    items: list[ShoppingItem] = field(default_factory=list)
    total_found: int = 0
    price_min: int | None = None
    price_max: int | None = None
    price_avg: int | None = None
    price_median: int | None = None
    error: str | None = None


def _parse_price(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = int(value)
        return number if number > 0 else None

    text = str(value)
    cleaned = re.sub(r"[^0-9]", "", text)
    if not cleaned:
        return None
    try:
        number = int(cleaned)
    except Exception:
        return None
    return number if number > 0 else None


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


async def search_google_shopping(query: str) -> ShoppingSummary:
    summary = ShoppingSummary(query_used=(query or "").strip())
    if not summary.query_used:
        summary.error = "Query kosong"
        return summary

    if not SERPAPI_KEY:
        summary.error = "SERPAPI_KEY belum di-set"
        return summary

    params = {
        "engine": "google_shopping",
        "q": summary.query_used,
        "api_key": SERPAPI_KEY,
        "gl": GOOGLE_SHOPPING_GL,
        "hl": GOOGLE_SHOPPING_HL,
        "num": GOOGLE_SHOPPING_NUM,
    }

    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        summary.error = f"Request gagal: {str(exc)[:160]}"
        return summary

    raw_items = data.get("shopping_results") or []
    items: list[ShoppingItem] = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or "")
        store = str(raw.get("source") or raw.get("merchant") or "")
        price_text = str(raw.get("price") or raw.get("extracted_price") or "")
        price = _parse_price(raw.get("extracted_price") or raw.get("price"))
        link = str(raw.get("product_link") or raw.get("link") or "")

        if not title:
            continue

        items.append(
            ShoppingItem(
                title=title,
                store=store,
                price=price,
                price_text=price_text,
                link=link,
            )
        )

    summary.items = items
    summary.total_found = len(items)

    prices = [item.price for item in items if item.price]
    if prices:
        summary.price_min = min(prices)
        summary.price_max = max(prices)
        summary.price_avg = sum(prices) // len(prices)
        summary.price_median = _median(prices)

    if not items and not summary.error:
        summary.error = "Tidak ada hasil shopping"

    return summary
