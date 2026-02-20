import os
import google.generativeai as genai
from dotenv import load_dotenv
import sys

# Encoding fix for Windows console
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: API Key not found in environment.")
    sys.exit(1)

genai.configure(api_key=api_key)

models_to_check = ["gemini-1.5-flash", "gemini-pro", "gemini-1.0-pro", "gemini-1.5-pro"]

print("--- API Check Start ---")
try:
    print(f"Key configured: {api_key[:5]}...")
    
    available_models = []
    print("Listing models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            available_models.append(m.name)
            
    print(f"Found {len(available_models)} models.")
    for m in available_models:
        print(f" - {m}")

    print("\nTesting specific models:")
    for model_name in models_to_check:
        try:
            print(f"Testing {model_name}...", end=" ")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content("Hello")
            print("OK")
        except Exception as e:
            print(f"FAIL: {e}")

except Exception as e:
    print(f"CRITICAL ERROR: {e}")
    import traceback
    traceback.print_exc()

print("--- API Check End ---")
