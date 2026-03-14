"""
photo_handler.py
────────────────
Handler utama untuk pesan foto dari user.
Flow: Terima foto → Analisis AI → Cari harga → Kirim hasil
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

from services.vision_service import ItemAnalysis
from services.price_aggregator import aggregate_prices
from utils.message_formatter import (
    format_price_summary,
)

logger = logging.getLogger(__name__)

PROCESSING_LOCK_KEY = "processing_photo"


def _extract_query_from_message(message) -> str:
    """Ambil keyword pencarian dari caption/text/reply text."""
    # 1) Caption pada foto
    if getattr(message, "caption", None):
        return message.caption.strip()

    # 2) Jika user reply ke pesan teks berisi nama barang
    reply_msg = getattr(message, "reply_to_message", None)
    if reply_msg:
        if getattr(reply_msg, "text", None):
            return reply_msg.text.strip()
        if getattr(reply_msg, "caption", None):
            return reply_msg.caption.strip()

    return ""


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Dipanggil setiap kali user mengirim foto ke bot.
    """
    message = update.effective_message
    if not message or not message.photo:
        return

    # Cegah spam: jika masih ada proses sebelumnya di chat yang sama
    if context.chat_data.get(PROCESSING_LOCK_KEY):
        await message.reply_text(
            "⏳ Permintaan sebelumnya masih diproses. Tunggu sebentar ya."
        )
        return

    status_msg = None
    context.chat_data[PROCESSING_LOCK_KEY] = True

    try:
        # ── 1. Kirim pesan "sedang memproses" (plain text, tanpa Markdown) ──
        status_msg = await message.reply_text(
            "🔍 Sedang memproses...\n\n"
            "Mode manual: saya akan cari berdasarkan keyword dari caption/reply."
        )

        # ── 2. Ambil keyword manual ────────────────────────────────────────
        query = _extract_query_from_message(message)
        if not query:
            await status_msg.edit_text(
                "❌ Keyword belum ada.\n\n"
                "Kirim foto + caption nama barang.\n"
                "Contoh: `iPhone 12 128GB`\n"
                "Atau reply foto ke pesan teks nama barang.",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

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

        # ── 4. Cari harga di marketplace ───────────────────────────────────
        await status_msg.edit_text(
            "🛒 Sedang mencari harga di Tokopedia & OLX..."
        )

        price_summary = await aggregate_prices(analysis)

        # ── 5. Kirim hasil taksiran ────────────────────────────────────────
        result_text = format_price_summary(price_summary)

        await status_msg.edit_text(
            result_text,
            parse_mode=ParseMode.MARKDOWN_V2,
            disable_web_page_preview=True,
        )

        logger.info(
            "Berhasil memproses foto: %s | %d hasil ditemukan",
            analysis.item_name,
            price_summary.total_found,
        )

    except Exception as exc:
        logger.exception("Error saat memproses foto: %s", exc)
        try:
            error_text = f"❌ Terjadi kesalahan:\n{str(exc)[:300]}"
            if status_msg is not None:
                await status_msg.edit_text(error_text)
            else:
                await message.reply_text(error_text)
        except Exception:
            pass
    finally:
        context.chat_data[PROCESSING_LOCK_KEY] = False
