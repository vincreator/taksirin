"""
price_aggregator.py
───────────────────
Mengumpulkan hasil dari semua marketplace secara paralel,
menghitung statistik harga, dan menyusun laporan taksiran.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from statistics import mean, median
from typing import Optional

from services.vision_service import ItemAnalysis
from services.tokopedia_service import TokopediaProduct, search_tokopedia
from services.olx_service import OLXProduct, search_olx

logger = logging.getLogger(__name__)


@dataclass
class PriceResult:
    """Satu entri harga dari marketplace mana pun."""
    source: str       # "Tokopedia" / "OLX"
    name: str
    price: int
    price_text: str
    url: str
    location: str = ""
    extra: str = ""   # Informasi tambahan (rating, terjual, dll.)


@dataclass
class PriceSummary:
    """Ringkasan taksiran harga dari semua sumber."""
    item_analysis: ItemAnalysis
    results: list[PriceResult] = field(default_factory=list)
    
    # Statistik (dihitung otomatis)
    price_min: int = 0
    price_max: int = 0
    price_avg: int = 0
    price_median: int = 0
    total_found: int = 0

    def calculate_stats(self) -> None:
        """Hitung statistik dari results yang ada."""
        valid_prices = [r.price for r in self.results if r.price > 0]
        self.total_found = len(self.results)
        if valid_prices:
            self.price_min = min(valid_prices)
            self.price_max = max(valid_prices)
            self.price_avg = int(mean(valid_prices))
            self.price_median = int(median(valid_prices))


async def aggregate_prices(analysis: ItemAnalysis) -> PriceSummary:
    """
    Cari harga dari semua marketplace secara paralel.

    Args:
        analysis: Hasil analisis gambar dari vision_service

    Returns:
        PriceSummary berisi semua hasil dan statistik
    """
    summary = PriceSummary(item_analysis=analysis)

    # Build beberapa variasi query agar lebih toleran typo/format
    seed_query = (analysis.item_name or "").strip()
    if analysis.search_keywords:
        seed_query = " ".join(analysis.search_keywords[:2]).strip() or seed_query

    queries = _build_query_variants(seed_query)
    logger.info("Mencari harga untuk: '%s' | variants=%s", seed_query, queries)

    tokopedia_products: list[TokopediaProduct] = []
    olx_products: list[OLXProduct] = []

    # Coba setiap variant sampai ada hasil
    for q in queries:
        t_task = asyncio.create_task(_safe_search_tokopedia(q))
        o_task = asyncio.create_task(_safe_search_olx(q))
        t_res, o_res = await asyncio.gather(t_task, o_task)

        if t_res:
            tokopedia_products.extend(t_res)
        if o_res:
            olx_products.extend(o_res)

        # Kalau sudah cukup data, stop lebih cepat
        if len(tokopedia_products) + len(olx_products) >= 6:
            break

    tokopedia_products = _dedupe_tokopedia(tokopedia_products)
    olx_products = _dedupe_olx(olx_products)

    # Konversi ke PriceResult
    for p in tokopedia_products:
        summary.results.append(
            PriceResult(
                source="Tokopedia",
                name=p.name,
                price=p.price,
                price_text=p.price_text,
                url=p.url,
                location=p.location,
                extra=f"⭐ {p.rating}" if p.rating else "",
            )
        )

    for p in olx_products:
        summary.results.append(
            PriceResult(
                source="OLX",
                name=p.name,
                price=p.price,
                price_text=p.price_text,
                url=p.url,
                location=p.location,
            )
        )

    summary.calculate_stats()
    return summary


async def _safe_search_tokopedia(query: str) -> list[TokopediaProduct]:
    try:
        return await search_tokopedia(query)
    except Exception as exc:
        logger.error("Tokopedia search gagal: %s", exc)
        return []


async def _safe_search_olx(query: str) -> list[OLXProduct]:
    try:
        return await search_olx(query)
    except Exception as exc:
        logger.error("OLX search gagal: %s", exc)
        return []


def _build_query_variants(query: str) -> list[str]:
    """Buat beberapa variasi query untuk meningkatkan kemungkinan match."""
    q = (query or "").strip()
    if not q:
        return []

    variants: list[str] = [q]

    # pisahkan huruf+angka: tempo4 -> tempo 4
    split_alnum = re.sub(r"([a-zA-Z])([0-9])", r"\1 \2", q)
    split_alnum = re.sub(r"([0-9])([a-zA-Z])", r"\1 \2", split_alnum)
    if split_alnum != q:
        variants.append(split_alnum)

    # versi lower
    lower_q = q.lower()
    if lower_q not in variants:
        variants.append(lower_q)

    # keyword tanpa token sangat pendek
    tokens = re.findall(r"[a-zA-Z0-9]+", q.lower())
    filtered = [t for t in tokens if len(t) >= 3]
    if filtered:
        compact = " ".join(filtered)
        if compact and compact not in variants:
            variants.append(compact)

        # fallback kata terkuat terakhir (mis. model)
        if len(filtered) >= 2:
            tail = " ".join(filtered[-2:])
            if tail not in variants:
                variants.append(tail)
            if filtered[-1] not in variants:
                variants.append(filtered[-1])

    # unique, preserve order
    return list(dict.fromkeys([v for v in variants if v]))[:6]


def _dedupe_tokopedia(items: list[TokopediaProduct]) -> list[TokopediaProduct]:
    seen: set[str] = set()
    out: list[TokopediaProduct] = []
    for item in items:
        key = (item.url or item.name or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_olx(items: list[OLXProduct]) -> list[OLXProduct]:
    seen: set[str] = set()
    out: list[OLXProduct] = []
    for item in items:
        key = (item.url or item.name or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
