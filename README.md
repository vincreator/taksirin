# TaksirinBot 🏷️

Bot Telegram untuk menaksir harga barang hanya dari foto, menggunakan AI Vision + scraping marketplace Indonesia.

## Fitur

- 📸 Kirim foto → bot langsung identifikasi barang pakai **GPT-4o Vision**
- 🛍️ Cari harga otomatis di **Tokopedia** & **OLX Indonesia**
- 📊 Tampilkan statistik harga: terendah, tertinggi, rata-rata, median
- 🔗 Link langsung ke listing yang ditemukan

## Struktur Project

```
taksirin/
├── bot.py                      # Entry point utama
├── config.py                   # Konfigurasi & env variables
├── requirements.txt
├── .env                        # API Keys (jangan di-commit!)
├── handlers/
│   ├── photo_handler.py        # Handler foto dari user
│   └── text_handler.py         # Handler /start, /help, teks biasa
├── services/
│   ├── vision_service.py       # OpenAI GPT-4o Vision
│   ├── tokopedia_service.py    # Scraper Tokopedia
│   ├── olx_service.py          # Scraper OLX Indonesia
│   └── price_aggregator.py     # Gabungkan hasil semua sumber
└── utils/
    └── message_formatter.py    # Format pesan Telegram
```

## Setup

### 1. Dapatkan API Keys

- **Telegram Bot Token**: Chat dengan [@BotFather](https://t.me/BotFather) → `/newbot`
- **OpenAI API Key**: [platform.openai.com/api-keys](https://platform.openai.com/api-keys)

### 2. Isi file `.env`

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Install & Jalankan

```bash
# Aktivasi virtual environment
source .venv/bin/activate

# Jalankan bot
python bot.py
```

## Cara Pakai

1. Cari bot kamu di Telegram
2. Kirim `/start`
3. Kirim foto barang
4. Bot akan analisis dan kirim hasil taksiran harga

## Flow Teknis

```
User kirim foto
    ↓
Download foto (resolusi tertinggi)
    ↓
OpenAI GPT-4o Vision → identifikasi barang + keyword
    ↓
Parallel search:
  ├─ Tokopedia API (ace.tokopedia.com)
  └─ OLX Indonesia (scraping HTML + __NEXT_DATA__)
    ↓
Hitung statistik harga
    ↓
Format & kirim ke user
```

## Catatan

- Estimasi harga bergantung pada ketersediaan listing di marketplace
- GPT-4o memerlukan foto yang cukup jelas untuk identifikasi akurat
- Harga marketplace dapat berubah sewaktu-waktu
