import httpx, os
from dotenv import load_dotenv
load_dotenv()
key = os.getenv('GEMINI_API_KEY')
print(f"Key: {key[:15]}...")

# Test endpoint native Gemini
url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
body = {
    "model": "gemini-2.0-flash",
    "messages": [{"role": "user", "content": "Reply only: OK"}],
    "max_tokens": 10
}
r = httpx.post(url, headers=headers, json=body, timeout=15)
print(f"Status: {r.status_code}")
print(r.text[:300])
