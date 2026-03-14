import os
from dotenv import load_dotenv

load_dotenv()

# ─── Telegram ───────────────────────────────────────────────────────────────
BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ─── AI Provider ─────────────────────────────────────────────────────────────
AI_PROVIDER: str = os.getenv("AI_PROVIDER", "gemini").strip().lower()

# ─── Google Gemini ───────────────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")

# ─── Groq ────────────────────────────────────────────────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

AI_PROVIDER_LABEL: str = "Groq" if AI_PROVIDER == "groq" else "Gemini"

# ─── Validasi ────────────────────────────────────────────────────────────────
if not BOT_TOKEN:
    raise ValueError("❌  TELEGRAM_BOT_TOKEN belum di-set di file .env")

if AI_PROVIDER not in {"gemini", "groq"}:
    raise ValueError("❌  AI_PROVIDER harus 'gemini' atau 'groq'")

if AI_PROVIDER == "gemini" and not GEMINI_API_KEY:
    raise ValueError("❌  GEMINI_API_KEY belum di-set di file .env")

if AI_PROVIDER == "groq" and not GROQ_API_KEY:
    raise ValueError("❌  GROQ_API_KEY belum di-set di file .env")
