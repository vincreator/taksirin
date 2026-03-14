"""
bot.py
──────
Entry point utama TaksirinBot.
Jalankan dengan: python bot.py
"""

import logging

from telegram import Update
from telegram.error import BadRequest, Conflict
from telegram.ext import (
    Application,
    ContextTypes,
    CommandHandler,
)

from config import BOT_TOKEN
from handlers.text_handler import handle_start, handle_help, handle_taksir

# ─── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
# Kurangi spam dari library
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


async def handle_app_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Tangani error global agar log tidak spam/noisy."""
    err = context.error
    if isinstance(err, Conflict):
        logger.warning("Bot conflict: ada instance lain yang sedang jalan.")
        return

    if isinstance(err, BadRequest) and "can't parse entities" in str(err).lower():
        logger.warning("BadRequest Markdown entity: %s", err)
        return

    logger.exception("Unhandled application error: %s", err)


def main() -> None:
    """Inisialisasi dan jalankan bot."""
    logger.info("🚀 TaksirinBot sedang starting...")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Daftarkan handlers ────────────────────────────────────────────────
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("help", handle_help))
    app.add_handler(CommandHandler("taksir", handle_taksir))
    app.add_error_handler(handle_app_error)

    logger.info("✅ Bot siap! Menunggu pesan masuk...")

    # ── Mulai polling ────────────────────────────────────────────────────
    app.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
