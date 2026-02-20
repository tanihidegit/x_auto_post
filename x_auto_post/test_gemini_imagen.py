import os
import google.generativeai as genai
from dotenv import load_dotenv
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

try:
    model_name = "gemini-2.0-flash-exp-imagen" # Exact name from raw list
    # remove 'models/' prefix if library adds it, or keep it if needed. library usually adds it?
    # Actually raw list had 'models/gemini...'. Library expects 'gemini...' usually.
    # Let's try omitting prefix first
    
    print(f"Testing {model_name} for image generation...")
    model = genai.GenerativeModel(model_name)
    response = model.generate_content("Generate an image of a cat")
    
    print("Response received.")
    print(response.text)
    # Check if parts contain image?
    if response.parts:
        for part in response.parts:
            print(f"Part type: {type(part)}")
            print(part)

except Exception as e:
    import traceback
    traceback.print_exc()
