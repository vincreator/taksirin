# TaksirinBot 🏷️

Bot Telegram untuk membantu menaksir harga barang berbasis teks menggunakan provider AI seperti Gemini atau Groq.

## Fitur

- 📝 Analisis hanya lewat command `/taksir`
- 🤖 Gemini atau Groq merapikan query dan memahami konteks barang
- 💰 Bot memberi estimasi harga, kategori, merek, dan tingkat keyakinan
- 🔎 Bot memberi keyword pencarian yang lebih tepat
- 🔒 Chat private bisa dibatasi hanya untuk owner tertentu

## Struktur Project

```
taksirin/
├── bot.py
├── config.py
├── requirements.txt
├── handlers/
│   └── text_handler.py
├── services/
│   └── vision_service.py
└── utils/
    └── message_formatter.py
```

## Setup

### 1. Dapatkan API Keys

- **Telegram Bot Token**: chat dengan [@BotFather](https://t.me/BotFather) lalu buat bot baru
- **Gemini API Key**: ambil dari Google AI Studio
- **Groq API Key**: ambil dari Groq Console jika ingin pakai Groq

### 2. Isi file `.env`

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OWNER_TELEGRAM_ID=123456789
AI_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.0-flash-lite
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

Untuk pindah ke Groq, cukup ubah:

```env
AI_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=llama-3.1-8b-instant
```

### 3. Install & Jalankan

```bash
source .venv/bin/activate
pip install -r requirements.txt
python bot.py
```

## Cara Pakai

1. Jalankan bot
2. Kirim `/start`
3. Kirim command seperti `/taksir iPhone 13 128GB` atau `/taksir Honda Beat 2022`
4. Bot akan mengembalikan ringkasan analisis dan estimasi harga

## Catatan

- Hasil terbaik didapat dari query yang spesifik
- Jika provider AI sedang rate limit, bot akan memakai fallback analisis sederhana
- Estimasi harga tetap bersifat perkiraan, bukan harga pasar final
