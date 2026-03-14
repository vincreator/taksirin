"""
text_handler.py
───────────────
Handler untuk command /start, /help, dan pencarian teks.
"""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import AI_PROVIDER_LABEL
from services.vision_service import analyze_text
from utils.message_formatter import format_ai_summary


WELCOME_MESSAGE = """
👋 *Selamat datang di TaksirinBot\\!*

Saya bisa menaksir harga barang dengan *AI text*\\!

📝 *Cara pakai:*
• Kirim *teks nama barang* \\(contoh: `iPhone 12 128GB`\\)

🔍 *Yang saya lakukan:*
1\\. Rapikan keyword dengan AI
2\\. Pahami merek, kategori, dan konteks barang
3\\. Tampilkan estimasi harga dan keyword yang lebih tepat

💡 *Tips agar hasil akurat:*
• Tulis merek \\+ model \\+ kapasitas/seri
• Contoh: `Samsung S23 Ultra 256GB`

🚀 Langsung kirim keyword barang kamu sekarang\\!
"""

HELP_MESSAGE = """
📖 *Bantuan TaksirinBot*

*Command:*
/start \\- Mulai bot & tampilkan panduan
/help  \\- Tampilkan pesan ini

*Cara menggunakan:*
Kirim teks nama barang → bot analisis dan beri estimasi harga

*Dibuat oleh:*
🤖 @XiXUGi
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
    """Handler teks: AI memahami query lalu memberi estimasi harga."""
    message = update.effective_message
    if not message or not message.text:
        return

    query = message.text.strip()
    if not query:
        return

    status_msg = await message.reply_text(f"🔍 Menganalisis barang dengan {AI_PROVIDER_LABEL}...")

    analysis = await analyze_text(query)
    result_text = format_ai_summary(analysis)

    await status_msg.edit_text(
        result_text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )

