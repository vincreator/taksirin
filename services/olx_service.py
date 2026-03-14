"""
olx_service.py
──────────────
Mencari harga barang di OLX Indonesia (olx.co.id) via scraping.
Mengekstrak data dari __NEXT_DATA__ JSON yang ada di halaman HTML.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from config import DEFAULT_HEADERS, MAX_RESULTS_PER_SOURCE

logger = logging.getLogger(__name__)

OLX_SEARCH_URL = "https://www.olx.co.id/items/q-{query}"
OLX_API_URL = "https://www.olx.co.id/api/relevance/v4/search"

HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://www.olx.co.id/",
}

OLX_BLOCK_UNTIL: float = 0.0


@dataclass
class OLXProduct:
    name: str
    price: int           # dalam Rupiah (0 jika "Harga belum ditentukan")
    price_text: str
    location: str
    url: str
    image_url: str
    date_posted: str = ""


async def search_olx(query: str) -> list[OLXProduct]:
    """
    Cari iklan di OLX berdasarkan kata kunci.

    Args:
        query: Kata kunci pencarian

    Returns:
        List OLXProduct
    """
    global OLX_BLOCK_UNTIL

    now = time.monotonic()
    if OLX_BLOCK_UNTIL > now:
        remaining = int(OLX_BLOCK_UNTIL - now)
        logger.info("OLX sementara di-skip %ss lagi (circuit breaker aktif)", remaining)
        return []

    # Coba API endpoint dulu, fallback ke scraping HTML
    products = await _search_via_api(query)
    if not products:
        products = await _search_via_html(query)

    logger.info("OLX: %d produk ditemukan untuk '%s'", len(products), query)
    return products


async def _search_via_api(query: str) -> list[OLXProduct]:
    """Gunakan OLX API internal."""
    params = {
        "clientId": "pwa",
        "clientVersion": "11.0.3",
        "location": "1000000",   # Seluruh Indonesia
        "q": query,
        "page": 1,
        "category": "0",
    }
    headers = {
        **HEADERS,
        "Accept": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }

    max_attempts = 2
    data = None

    try:
        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    headers=headers,
                    timeout=5.0,
                    follow_redirects=True,
                    trust_env=False,
                ) as client:
                    resp = await client.get(OLX_API_URL, params=params)

                if resp.status_code != 200:
                    logger.info(
                        "OLX API status %s untuk query '%s' (fallback HTML)",
                        resp.status_code,
                        query,
                    )
                    return []

                data = resp.json()
                break
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.info("OLX API request error untuk query '%s': %r (fallback HTML)", query, exc)
                return []

        products = []
        ads = (data or {}).get("data", []) or (data or {}).get("ads", []) or []

        for ad in ads[:MAX_RESULTS_PER_SOURCE]:
            price_int, price_text = _extract_price(ad)
            products.append(
                OLXProduct(
                    name=ad.get("title", ""),
                    price=price_int,
                    price_text=price_text,
                    location=_extract_location(ad),
                    url=_extract_url(ad),
                    image_url=_extract_image(ad),
                    date_posted=ad.get("display_date", "") or ad.get("created_at", ""),
                )
            )
        return products

    except Exception as exc:
        logger.warning("OLX API gagal untuk query '%s': %r", query, exc)
        return []


async def _search_via_html(query: str) -> list[OLXProduct]:
    """Scrape halaman HTML OLX sebagai fallback."""
    # OLX format URL: spasi jadi tanda hubung
    slug = re.sub(r"\s+", "-", query.strip().lower())
    url = OLX_SEARCH_URL.format(query=quote(slug, safe="-"))

    try:
        max_attempts = 2
        html = ""

        for attempt in range(1, max_attempts + 1):
            try:
                async with httpx.AsyncClient(
                    headers=HEADERS,
                    timeout=6.0,
                    follow_redirects=True,
                    trust_env=False,
                ) as client:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    html = resp.text
                break
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * attempt)
                    continue
                logger.info("OLX HTML request timeout/error untuk query '%s': %r", query, exc)
                return []

        # Coba ekstrak __NEXT_DATA__
        products = _parse_next_data(html)
        if products:
            return products

        # Fallback: parse HTML biasa
        return _parse_html_cards(html)

    except Exception as exc:
        global OLX_BLOCK_UNTIL
        OLX_BLOCK_UNTIL = time.monotonic() + 120
        logger.warning("OLX HTML scraping gagal untuk query '%s': %r. Pause 120s.", query, exc)
        return []


def _parse_next_data(html: str) -> list[OLXProduct]:
    """Ekstrak data dari tag <script id='__NEXT_DATA__'>."""
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not match:
        return []

    try:
        data = json.loads(match.group(1))
        # Navigasi ke dalam struktur data Next.js
        ads = (
            data.get("props", {})
            .get("pageProps", {})
            .get("ads", [])
            or data.get("props", {})
            .get("initialState", {})
            .get("listings", {})
            .get("ads", [])
        )

        products = []
        for ad in ads[:MAX_RESULTS_PER_SOURCE]:
            price_int, price_text = _extract_price(ad)
            products.append(
                OLXProduct(
                    name=ad.get("title", ""),
                    price=price_int,
                    price_text=price_text,
                    location=_extract_location(ad),
                    url=_extract_url(ad),
                    image_url=_extract_image(ad),
                )
            )
        return products

    except Exception as exc:
        logger.warning("Parse __NEXT_DATA__ gagal: %s", exc)
        return []


def _parse_html_cards(html: str) -> list[OLXProduct]:
    """Parse kartu iklan dari HTML standar OLX."""
    soup = BeautifulSoup(html, "lxml")
    products = []

    cards = soup.select("li[data-aut-id='itemBox']")
    for card in cards[:MAX_RESULTS_PER_SOURCE]:
        try:
            title_el = card.select_one("[data-aut-id='itemTitle']")
            price_el = card.select_one("[data-aut-id='itemPrice']")
            loc_el = card.select_one("[data-aut-id='item-location']")
            link_el = card.select_one("a")
            img_el = card.select_one("img")

            name = title_el.get_text(strip=True) if title_el else ""
            price_text = price_el.get_text(strip=True) if price_el else "Harga belum ditentukan"
            price_int = _price_from_text(price_text)
            location = loc_el.get_text(strip=True) if loc_el else ""
            url = link_el.get("href", "") if link_el else ""
            if url and not url.startswith("http"):
                url = "https://www.olx.co.id" + url
            image_url = img_el.get("src", "") if img_el else ""

            if name:
                products.append(
                    OLXProduct(
                        name=name,
                        price=price_int,
                        price_text=price_text,
                        location=location,
                        url=url,
                        image_url=image_url,
                    )
                )
        except Exception:
            continue

    return products


# ─── Helper functions ──────────────────────────────────────────────────────

def _extract_price(ad: dict) -> tuple[int, str]:
    price = ad.get("price", {})
    if isinstance(price, dict):
        # Format OLX terbaru: price.value.raw + price.value.display
        nested = price.get("value", {})
        if isinstance(nested, dict):
            raw = nested.get("raw", 0)
            display = nested.get("display", "")
            if isinstance(raw, (int, float)):
                return int(raw), display or f"Rp {int(raw):,}"

        text = price.get("display", "") or ""
        value = price.get("value", 0)
        if isinstance(value, (int, float)):
            return int(value), text or f"Rp {int(value):,}"
        return _price_from_text(str(text)), str(text) or "Harga belum ditentukan"
    if isinstance(price, (int, float)):
        return int(price), f"Rp {int(price):,}"
    return 0, "Harga belum ditentukan"


def _extract_location(ad: dict) -> str:
    loc_resolved = ad.get("locations_resolved", {})
    if isinstance(loc_resolved, dict):
        city = loc_resolved.get("ADMIN_LEVEL_3_name", "")
        district = loc_resolved.get("SUBLOCALITY_LEVEL_1_name", "")
        if city and district:
            return f"{district}, {city}"
        if city:
            return city

    loc = ad.get("locations", [{}])
    if isinstance(loc, list) and loc:
        return loc[0].get("name", "")
    return ad.get("location", {}).get("city", "") or ""


def _extract_url(ad: dict) -> str:
    url = ad.get("url", "") or ad.get("permalink", "")
    if url and not url.startswith("http"):
        url = "https://www.olx.co.id" + url
    if not url:
        ad_id = str(ad.get("ad_id", "") or ad.get("id", "")).strip()
        title = str(ad.get("title", "")).strip()
        if ad_id:
            slug = _slugify(title)[:80] or "item"
            url = f"https://www.olx.co.id/item/{slug}-iid-{ad_id}"
    return url


def _extract_image(ad: dict) -> str:
    images = ad.get("images", [{}]) or ad.get("image", [{}])
    if isinstance(images, list) and images:
        first = images[0]
        if isinstance(first, dict):
            return first.get("url", "") or first.get("thumbnail", "")
        return str(first)
    return ""


def _price_from_text(text: str) -> int:
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else 0


def _slugify(text: str) -> str:
    value = (text or "").strip().lower()
    value = re.sub(r"[^a-z0-9\s-]", "", value)
    value = re.sub(r"\s+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value
