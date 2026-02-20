import os
import google.generativeai as genai
from dotenv import load_dotenv
import traceback

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

try:
    print(f"API Key: {api_key[:5]}...{api_key[-5:] if api_key else 'None'}")
    
    print("Listing models...")
    for m in genai.list_models():
        print(f"Model: {m.name} ({m.supported_generation_methods})")
    
    print("\nGenerating content with gemini-pro...")
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content("Hello")
    print(f"Response: {response.text}")

except Exception:
    with open("error.log", "w") as f:
        traceback.print_exc(file=f)
    traceback.print_exc()
