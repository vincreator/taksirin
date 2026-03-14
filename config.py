import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ───────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
OWNER_TELEGRAM_ID_RAW: str = os.getenv("OWNER_TELEGRAM_ID", "").strip()
OWNER_TELEGRAM_ID: int | None = int(OWNER_TELEGRAM_ID_RAW) if OWNER_TELEGRAM_ID_RAW else None

# ─── AI Provider ─────────────────────────────────────────────────────────────
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").strip().lower()

# ─── Google Gemini ───────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")

# ─── Groq ────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

AI_PROVIDER_LABEL: str = "Groq" if AI_PROVIDER == "groq" else "Gemini"

# ─── Online market lookup (Google Shopping via SerpAPI) ───────────────────
SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
GOOGLE_SHOPPING_GL: str = os.getenv("GOOGLE_SHOPPING_GL", "id")
GOOGLE_SHOPPING_HL: str = os.getenv("GOOGLE_SHOPPING_HL", "id")
GOOGLE_SHOPPING_NUM: int = int(os.getenv("GOOGLE_SHOPPING_NUM", "10"))

# ─── Validasi ────────────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise ValueError("❌  TELEGRAM_BOT_TOKEN belum di-set di file .env")

if AI_PROVIDER not in {"gemini", "groq"}:
    raise ValueError("❌  AI_PROVIDER harus 'gemini' atau 'groq'")

if AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
    raise ValueError("❌  GEMINI_API_KEY belum di-set di file .env")

if AI_PROVIDER == "groq" and not GROQ_API_KEY:
    raise ValueError("❌  GROQ_API_KEY belum di-set di file .env")
