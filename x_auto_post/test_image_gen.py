import sys
import os
import io

# Encoding fix
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from src.image_generator import generate_image

prompt = "A warm photograph of a craftsman-style wooden kitchen counter with a bowl of steaming ramen and a glass of beer at night. Soft pendant lighting. Film grain."

print(f"Testing image generation with prompt: {prompt}")
result = generate_image(prompt)

if result:
    print(f"Success! Image saved to: {result}")
else:
    print("Failed to generate image.")
