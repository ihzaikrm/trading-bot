import requests, os
from dotenv import load_dotenv
load_dotenv()

token = os.getenv('TELEGRAM_BOT_TOKEN')
chat_id = os.getenv('TELEGRAM_CHAT_ID')

print(f"Token: {token[:20]}...")
print(f"Chat ID: {chat_id}")

# Test kirim
r = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    json={"chat_id": chat_id, "text": "Test dari trading bot!"},
    timeout=10
)
print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
