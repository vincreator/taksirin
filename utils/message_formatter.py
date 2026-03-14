"""
message_formatter.py
─────────────────────
Membuat pesan Telegram yang rapi dari hasil analisis AI.
"""

from __future__ import annotations

from services.google_shopping_service import ShoppingSummary
from services.vision_service import ItemAnalysis


def format_ai_summary(analysis: ItemAnalysis) -> str:
    """Buat pesan lengkap hasil analisis AI text-only."""
    lines: list[str] = []
    condition_lower = (analysis.condition_guess or "").lower()
    if "bekas" in condition_lower or "second" in condition_lower or "seken" in condition_lower:
        price_label = "🤖 *Estimasi Harga Bekas:*"
    elif "baru" in condition_lower or "new" in condition_lower or "segel" in condition_lower:
        price_label = "🤖 *Estimasi Harga Baru:*"
    else:
        price_label = "🤖 *Estimasi Harga:*"

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
    if analysis.condition_score is not None:
        lines.append(f"📉 *Skor kondisi:* {_escape(str(analysis.condition_score))}/100")
    lines.append(f"{confidence_emoji} *Keyakinan ID:* {analysis.confidence.capitalize()}")

    if analysis.description:
        lines.append(f"📝 {_escape(analysis.description)}")

    if analysis.replaced_parts:
        lines.append("🔄 *Part yang disebut sudah diganti:*")
        for item in analysis.replaced_parts[:5]:
            lines.append(f"• {_escape(item)}")

    if analysis.known_defects:
        lines.append("⚠️ *Minus/Kendala yang terdeteksi:*")
        for item in analysis.known_defects[:6]:
            lines.append(f"• {_escape(item)}")

    if analysis.positive_notes:
        lines.append("✅ *Catatan positif:*")
        for item in analysis.positive_notes[:5]:
            lines.append(f"• {_escape(item)}")

    lines.append(f"📦 *Kelengkapan:* {_escape(analysis.completeness)}")
    lines.append(f"🛡️ *Garansi:* {_escape(analysis.warranty_status)}")
    lines.append(f"⏱️ *Estimasi pemakaian:* {_escape(analysis.usage_estimate)}")

    lines.append("")
    lines.append("─" * 30)

    # ── Estimasi harga dari AI ──────────────────────────────────────────────
    if analysis.estimated_price_min and analysis.estimated_price_max:
        lines.append("")
        lines.append(price_label)
        lines.append(
            f"   {_rp(analysis.estimated_price_min)} – {_rp(analysis.estimated_price_max)}"
        )
    else:
        lines.append("")
        lines.append(f"{price_label} belum cukup yakin untuk memberi angka spesifik")

    if analysis.search_keywords:
        lines.append("")
        lines.append("🔎 *Keyword yang disarankan:*")
        for keyword in analysis.search_keywords[:5]:
            lines.append(f"• {_escape(keyword)}")

    if analysis.pricing_notes:
        lines.append("")
        lines.append(f"🧠 *Catatan penyesuaian harga:* {_escape(analysis.pricing_notes)}")

    lines.append("")
    lines.append("─" * 30)

    lines.append("")
    lines.append("💡 Kirim query lebih spesifik untuk hasil lebih akurat, misalnya: `iPhone 13 Pro 256GB Sierra Blue`")

    if analysis.error:
        lines.append("")
        lines.append(f"⚠️ *Mode fallback aktif:* {_escape(analysis.error[:160])}")

    lines.append("")
    lines.append("_⚡ Powered by @XiXuGi_")

    return "\n".join(lines)


def format_error_message(error: str) -> str:
    """Pesan error umum."""
    return (
        f"❌ *Terjadi kesalahan*\n\n"
        f"`{_escape(error[:200])}`\n\n"
        f"Silakan coba lagi dengan query teks yang lebih spesifik\\."
    )


def format_online_summary(analysis: ItemAnalysis, summary: ShoppingSummary) -> str:
    lines: list[str] = []

    condition_lower = (analysis.condition_guess or "").lower()
    if "bekas" in condition_lower or "second" in condition_lower or "seken" in condition_lower:
        price_label = "🌐 *Harga Online Bekas:*"
    elif "baru" in condition_lower or "new" in condition_lower or "segel" in condition_lower:
        price_label = "🌐 *Harga Online Baru:*"
    else:
        price_label = "🌐 *Harga Online:*"

    lines.append("🏷️ *Hasil Taksir Online*")
    lines.append("")
    lines.append(f"📦 *Nama:* {_escape(analysis.item_name)}")
    lines.append(f"🔧 *Kondisi:* {_escape(analysis.condition_guess)}")
    lines.append(f"🔎 *Query online:* {_escape(summary.query_used)}")

    if summary.error:
        lines.append("")
        lines.append(f"⚠️ *Lookup online gagal:* {_escape(summary.error[:180])}")

    if summary.total_found > 0 and summary.price_min and summary.price_max:
        lines.append("")
        lines.append(price_label)
        lines.append(f"   {_rp(summary.price_min)} – {_rp(summary.price_max)}")
        lines.append(f"📊 *Ringkasan {summary.total_found} listing:*")
        lines.append(f"   • Rata\\-rata: {_rp(summary.price_avg)}")
        lines.append(f"   • Median: {_rp(summary.price_median)}")
    else:
        lines.append("")
        lines.append("⚠️ *Belum ada harga online yang valid dari listing yang ditemukan\\.*")

    if summary.items:
        lines.append("")
        lines.append("🛒 *Listing Google Shopping teratas:*")
        for idx, item in enumerate(summary.items[:5], start=1):
            title = _escape(item.title[:70] + ("…" if len(item.title) > 70 else ""))
            store = _escape(item.store) if item.store else "Toko tidak diketahui"
            price = _rp(item.price) if item.price else _escape(item.price_text or "Harga tidak tercantum")
            link = f"[Lihat]({item.link})" if item.link else ""
            lines.append(f"{idx}\\. {title}")
            lines.append(f"   • Toko: {store}")
            lines.append(f"   • Harga: {price} {link}")

    lines.append("")
    lines.append("─" * 30)
    lines.append("")
    lines.append("💡 Gunakan `/taksir` untuk analisis AI detail kondisi, atau `/taksir_online` untuk cek harga listing online terbaru")
    lines.append("")
    lines.append("_⚡ Powered by @XiXuGi_")

    return "\n".join(lines)


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
