# core/notifier.py
import requests
import os
import time

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def tg(msg):
    """Kirim pesan ke Telegram"""
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"[TG] Gagal: {e}")

def get_updates(offset=None):
    """Ambil pesan terbaru dari Telegram"""
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        params = {"timeout": 5, "offset": offset} if offset else {"timeout": 5}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("result", [])
    except Exception as e:
        print(f"[TG] Gagal getUpdates: {e}")
    return []

def send_message(chat_id, text):
    """Kirim balasan ke chat tertentu"""
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"[TG] Gagal reply: {e}")