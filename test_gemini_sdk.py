import os
from dotenv import load_dotenv
load_dotenv()
from google import genai

key = os.getenv('GEMINI_API_KEY')
print(f"Key: {key[:15]}...")
client = genai.Client(api_key=key)
r = client.models.generate_content(model='gemini-2.0-flash', contents='Reply only: OK')
print('SUCCESS:', r.text)
