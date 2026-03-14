import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ───────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ─── Google Gemini ───────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

# ─── Scraper settings ───────────────────────────────────────────────────────
MAX_RESULTS_PER_SOURCE: int = int(os.getenv("MAX_RESULTS_PER_SOURCE", "5"))

# ─── HTTP Headers (agar tidak di-block oleh marketplace) ────────────────────
DEFAULT_HEADERS: dict = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ─── Validasi ────────────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise ValueError("❌  TELEGRAM_BOT_TOKEN belum di-set di file .env")
if not GEMINI_API_KEY:
    raise ValueError("❌  GEMINI_API_KEY belum di-set di file .env")
