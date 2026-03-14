"""
text_handler.py
───────────────
Handler untuk command /start dan /help.
"""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.price_aggregator import aggregate_prices
from services.vision_service import ItemAnalysis
from utils.message_formatter import format_price_summary


WELCOME_MESSAGE = """
👋 *Selamat datang di TaksirinBot\\!*

Saya bisa menaksir harga barang dengan *scraping manual* dari keyword\\!

📸 *Cara pakai:*
• Kirim *teks nama barang* \\(contoh: `iPhone 12 128GB`\\)
• Atau kirim foto + caption nama barang

🔍 *Yang saya lakukan:*
1\\. Ambil keyword dari kamu
2\\. Cari harga di *Tokopedia* dan *OLX*
3\\. Tampilkan estimasi harga pasaran

💡 *Tips agar hasil akurat:*
• Tulis merek + model + kapasitas/seri
• Contoh: `Samsung S23 Ultra 256GB`

🚀 Langsung kirim keyword barang kamu sekarang\\!
"""

HELP_MESSAGE = """
📖 *Bantuan TaksirinBot*

*Command:*
/start \\- Mulai bot & tampilkan panduan
/help  \\- Tampilkan pesan ini

*Cara menggunakan:*
Kirim teks nama barang → bot cari harga di marketplace

*Didukung oleh:*
🛍️ Tokopedia
🏪 OLX Indonesia
"""


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /start."""
    await update.effective_message.reply_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /help."""
    await update.effective_message.reply_text(
        HELP_MESSAGE,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler teks biasa: langsung jadikan keyword pencarian manual."""
    message = update.effective_message
    if not message or not message.text:
        return

    query = message.text.strip()
    if not query:
        return

    status_msg = await message.reply_text("🔍 Mencari harga di Tokopedia & OLX...")

    analysis = ItemAnalysis(
        item_name=query,
        brand="Manual",
        category="Tidak diketahui",
        condition_guess="Tidak diketahui",
        description=f"Pencarian manual berdasarkan keyword: {query}",
        search_keywords=[query],
        estimated_price_min=None,
        estimated_price_max=None,
        confidence="high",
    )

    summary = await aggregate_prices(analysis)
    result_text = format_price_summary(summary)

    await status_msg.edit_text(
        result_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )
