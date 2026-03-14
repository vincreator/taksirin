"""
message_formatter.py
─────────────────────
Membuat pesan Telegram yang rapi dari hasil analisis & taksiran harga.
"""

from __future__ import annotations

from services.price_aggregator import PriceSummary
from services.vision_service import ItemAnalysis


def format_analyzing_message() -> str:
    """Pesan saat bot sedang memproses foto."""
    return (
        "🔍 *Sedang menganalisis foto...*\n\n"
        "_Mohon tunggu, saya sedang mengenali barang dan mencari harga di marketplace._"
    )


def format_item_not_found() -> str:
    """Pesan jika barang tidak berhasil diidentifikasi."""
    return (
        "❌ *Barang tidak berhasil diidentifikasi*\n\n"
        "Foto yang kamu kirim kurang jelas atau tidak menampilkan barang secara terlihat.\n\n"
        "💡 *Tips:*\n"
        "• Pastikan barang terlihat jelas di foto\n"
        "• Gunakan pencahayaan yang cukup\n"
        "• Foto dari depan/samping agar detail terlihat"
    )


def format_price_summary(summary: PriceSummary) -> str:
    """
    Buat pesan lengkap hasil taksiran harga.

    Args:
        summary: PriceSummary dari price_aggregator

    Returns:
        String pesan dalam format Markdown (Telegram MarkdownV2-safe)
    """
    analysis = summary.item_analysis
    lines: list[str] = []

    # ── Header identifikasi barang ──────────────────────────────────────────
    confidence_emoji = {"high": "✅", "medium": "🟡", "low": "🔴"}.get(
        analysis.confidence, "🟡"
    )
    lines.append(f"🏷️ *Hasil Identifikasi Barang*")
    lines.append("")
    lines.append(f"📦 *Nama:* {_escape(analysis.item_name)}")
    lines.append(f"🏭 *Merek:* {_escape(analysis.brand)}")
    lines.append(f"📂 *Kategori:* {_escape(analysis.category)}")
    lines.append(f"🔧 *Kondisi:* {_escape(analysis.condition_guess)}")
    lines.append(f"{confidence_emoji} *Keyakinan ID:* {analysis.confidence.capitalize()}")

    if analysis.description:
        lines.append(f"📝 {_escape(analysis.description)}")

    lines.append("")
    lines.append("─" * 30)

    # ── Estimasi harga dari AI ──────────────────────────────────────────────
    if analysis.estimated_price_min and analysis.estimated_price_max:
        lines.append("")
        lines.append("🤖 *Estimasi Harga \\(dari AI\\):*")
        lines.append(
            f"   {_rp(analysis.estimated_price_min)} – {_rp(analysis.estimated_price_max)}"
        )

    # ── Statistik harga dari marketplace ───────────────────────────────────
    if summary.total_found > 0 and summary.price_min > 0:
        lines.append("")
        lines.append(f"📊 *Taksiran Harga Marketplace \\({summary.total_found} iklan\\):*")
        lines.append(f"   🔻 Terendah : *{_rp(summary.price_min)}*")
        lines.append(f"   🔺 Tertinggi: *{_rp(summary.price_max)}*")
        lines.append(f"   📈 Rata\\-rata: *{_rp(summary.price_avg)}*")
        lines.append(f"   📉 Median   : *{_rp(summary.price_median)}*")
    elif summary.total_found == 0:
        lines.append("")
        lines.append("⚠️ _Tidak ada hasil ditemukan di marketplace\\._")
        lines.append("💡 Coba kirim keyword lebih spesifik: *merek + model + kapasitas/seri*")
        lines.append("   Contoh: `Infinix Note 40 256GB` atau `Honda Beat 2021`")

    lines.append("")
    lines.append("─" * 30)

    # ── Hasil per marketplace ───────────────────────────────────────────────
    tokopedia_items = [r for r in summary.results if r.source == "Tokopedia"]
    olx_items = [r for r in summary.results if r.source == "OLX"]

    if tokopedia_items:
        lines.append("")
        lines.append("🛍️ *Tokopedia:*")
        for i, item in enumerate(tokopedia_items[:5], 1):
            price_str = _rp(item.price) if item.price > 0 else "Nego"
            name_short = _escape(item.name[:50] + ("…" if len(item.name) > 50 else ""))
            location = f" · {_escape(item.location)}" if item.location else ""
            extra = f" {_escape(item.extra)}" if item.extra else ""
            url_text = f"[Lihat]({item.url})" if item.url else ""
            lines.append(
                f"  {i}\\. {name_short}\n"
                f"     💰 *{price_str}*{location}{extra} {url_text}"
            )

    if olx_items:
        lines.append("")
        lines.append("🏪 *OLX:*")
        for i, item in enumerate(olx_items[:5], 1):
            price_str = _rp(item.price) if item.price > 0 else "Nego"
            name_short = _escape(item.name[:50] + ("…" if len(item.name) > 50 else ""))
            location = f" · {_escape(item.location)}" if item.location else ""
            url_text = f"[Lihat]({item.url})" if item.url else ""
            lines.append(
                f"  {i}\\. {name_short}\n"
                f"     💰 *{price_str}*{location} {url_text}"
            )

    lines.append("")
    lines.append("─" * 30)
    lines.append("")
    lines.append("_⚡ Powered by Gemini Vision \\+ Tokopedia \\+ OLX_")

    return "\n".join(lines)


def format_error_message(error: str) -> str:
    """Pesan error umum."""
    return (
        f"❌ *Terjadi kesalahan*\n\n"
        f"`{_escape(error[:200])}`\n\n"
        f"Silakan coba lagi atau kirim foto yang berbeda\\."
    )


# ── Helpers ────────────────────────────────────────────────────────────────

def _rp(amount: int) -> str:
    """Format angka ke Rupiah dengan titik pemisah ribuan."""
    return f"Rp {amount:,}".replace(",", "\\.")


def _escape(text: str) -> str:
    """Escape karakter khusus MarkdownV2 Telegram."""
    special = r"\_*[]()~`>#+-=|{}.!"
    for ch in special:
        text = text.replace(ch, f"\\{ch}")
    return text
