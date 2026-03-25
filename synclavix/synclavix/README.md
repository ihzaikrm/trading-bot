# Synclavix – Autonomous AI Trading System

**Synclavix** adalah sistem trading otonom berbasis multi‑LLM adversarial yang dirancang untuk menghasilkan alpha secara konsisten, melindungi modal, dan mendistribusikan keuntungan untuk misi sosial. Sistem ini menggabungkan filter makro (DXY, momentum), narrative scanner, screener multi‑aset, dan 6 LLM yang berdebat untuk mencapai konsensus.

## 🧠 Arsitektur


## 📂 Struktur Proyek


## 🚀 Menjalankan

1. Install dependencies: `pip install -r requirements.txt`
2. Salin `.env.example` ke `.env` dan isi dengan kunci API Anda.
3. Jalankan: `py main.py` (dummy pipeline saat ini)

## 📊 Status

Saat ini dalam fase observasi. Bot utama berjalan di GitHub Actions setiap 2 jam. Setelah ada closed trade, sistem akan diintegrasikan dengan state management penuh.

## 🤝 Kontribusi

Kami menyambut kontribusi. Baca [CONTRIBUTING.md](docs/CONTRIBUTING.md) untuk panduan.

## 📜 Lisensi

MIT


## 🧪 Testing

Run tests with `pytest tests/` after installing dependencies.
