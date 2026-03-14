"""
text_handler.py
───────────────
Handler untuk command /start, /help, dan /taksir.
"""

from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from config import OWNER_TELEGRAM_ID
from services.google_shopping_service import search_google_shopping
from services.vision_service import analyze_text
from utils.message_formatter import format_ai_summary, format_online_summary


WELCOME_MESSAGE = """
👋 *Selamat datang di TaksirinBot\\!*

Saya bisa menaksir harga barang dengan *AI text*\\!

📝 *Cara pakai:*
• Pakai command */taksir* lalu isi nama barang
• Contoh: `/taksir iPhone 12 128GB`

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
/taksir <nama barang> \\- Analisis harga barang
/taksir_online <nama barang> \\- Cek harga online marketplace

*Cara menggunakan:*
Gunakan `/taksir nama barang` agar bot analisis dan beri estimasi harga

*Dibuat oleh:*
🤖 @XiXUGi
"""

PRIVATE_LOCK_MESSAGE = "⛔ Akses private bot ini khusus owner\\."
TAKSIR_USAGE_MESSAGE = "Gunakan command: `/taksir nama barang`\nContoh: `/taksir iphone 13 pro 256gb second`"
TAKSIR_ONLINE_USAGE_MESSAGE = "Gunakan command: `/taksir_online nama barang`\nContoh: `/taksir_online iphone 13 pro 256gb second`"


def _is_private_owner(update: Update) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    if not chat or not user:
        return False
    if chat.type != "private":
        return True
    if OWNER_TELEGRAM_ID is None:
        return False
    return user.id == OWNER_TELEGRAM_ID


async def _ensure_private_access(update: Update) -> bool:
    if _is_private_owner(update):
        return True
    message = update.effective_message
    if message:
        await message.reply_text(PRIVATE_LOCK_MESSAGE, parse_mode=ParseMode.MARKDOWN_V2)
    return False


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /start."""
    if not await _ensure_private_access(update):
        return
    await update.effective_message.reply_text(
        WELCOME_MESSAGE,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler untuk command /help."""
    if not await _ensure_private_access(update):
        return
    await update.effective_message.reply_text(
        HELP_MESSAGE,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_taksir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler command /taksir: AI memahami query lalu memberi estimasi harga."""
    if not await _ensure_private_access(update):
        return

    message = update.effective_message
    if not message:
        return

    query = " ".join(context.args).strip()
    if not query:
        await message.reply_text(TAKSIR_USAGE_MESSAGE, parse_mode=ParseMode.MARKDOWN_V2)
        return

    status_msg = await message.reply_text("🔍 Menganalisis barang dengan AI...")

    analysis = await analyze_text(query)
    result_text = format_ai_summary(analysis)

    await status_msg.edit_text(
        result_text,
        parse_mode=ParseMode.MARKDOWN_V2,
    )


async def handle_taksir_online(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler command /taksir_online: AI + lookup harga online Google Shopping."""
    if not await _ensure_private_access(update):
        return

    message = update.effective_message
    if not message:
        return

    query = " ".join(context.args).strip()
    if not query:
        await message.reply_text(TAKSIR_ONLINE_USAGE_MESSAGE, parse_mode=ParseMode.MARKDOWN_V2)
        return

    status_msg = await message.reply_text("🌐 Menganalisis barang dan mencari harga online...")

    analysis = await analyze_text(query)

    online_query = analysis.item_name or query
    condition_lower = (analysis.condition_guess or "").lower()
    if "bekas" in condition_lower and "bekas" not in online_query.lower() and "second" not in online_query.lower():
        online_query = f"{online_query} bekas"
    elif "baru" in condition_lower and "baru" not in online_query.lower() and "new" not in online_query.lower():
        online_query = f"{online_query} baru"

    summary = await search_google_shopping(online_query)
    result_text = format_online_summary(analysis, summary)

    await status_msg.edit_text(
        result_text,
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )

