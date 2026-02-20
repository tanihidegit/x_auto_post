import os
import requests
from dotenv import load_dotenv
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

print(f"Checking URL: ... (hidden key)")

try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        print(f"Models found: {len(data.get('models', []))}")
        for m in data.get('models', [])[:5]:
            print(f" - {m['name']}")
    else:
        print(f"Error Response: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
