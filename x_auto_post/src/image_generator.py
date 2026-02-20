import os
import requests
import json
import base64
import datetime
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

IMAGE_DIR = "generated_images"

def generate_image(prompt):
    """
    REST APIを使用して画像を生成し、ローカルに保存します。
    """
    if not api_key:
        print("GOOGLE_API_KEYが設定されていません。")
        return None

    os.makedirs(IMAGE_DIR, exist_ok=True)
    
    # 試行するモデルとエンドポイントのリスト
    # 1. Imagen 3.0 (v1beta) - 推奨
    # 2. Gemini 2.0 Flash Imagen (v1beta) - 代替
    
    endpoints = [
        {
            "url": f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict?key={api_key}",
            "payload": {
                "instances": [{"prompt": prompt}],
                "parameters": {"sampleCount": 1}
            },
            "name": "imagen-3.0-generate-001"
        },
        {
            # Gemini 2.0 Flash Imagen uses generateContent but might need specific config context
            # For simplicity, we try the predict endpoint first as it might be compatible or standard for image models
            "url": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-imagen:generateContent?key={api_key}",
            "payload": {
                "contents": [{"parts": [{"text": prompt}]}],
                 # Some experimental models might just take text and return image part
            },
            "name": "gemini-2.0-flash-exp-imagen"
        },
        {
            "url": f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp-imagen:predict?key={api_key}",
            "payload": {
                "instances": [{"prompt": prompt}],
                "parameters": {"sampleCount": 1}
            },
            "name": "gemini-2.0-flash-exp-imagen-predict"
        }
    ]

    for endpoint in endpoints:
        try:
            print(f"モデル {endpoint['name']} で画像生成を試行中...")
            response = requests.post(
                endpoint["url"],
                headers={"Content-Type": "application/json"},
                json=endpoint["payload"]
            )
            
            if response.status_code == 200:
                result = response.json()
                image_data = None
                
                # Imagen 3.0 response format
                if "predictions" in result:
                    # Usually returned as base64 in bytesBase64Encoded or similar
                    prediction = result["predictions"][0]
                    if "bytesBase64Encoded" in prediction:
                        image_data = base64.b64decode(prediction["bytesBase64Encoded"])
                    elif "mimeType" in prediction and "bytesBase64Encoded" in prediction: # valid structure
                         image_data = base64.b64decode(prediction["bytesBase64Encoded"])

                # Gemini response format
                elif "candidates" in result:
                     parts = result["candidates"][0]["content"]["parts"]
                     for part in parts:
                         if "inline_data" in part:
                             image_data = base64.b64decode(part["inline_data"]["data"])
                             break

                if image_data:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"image_{timestamp}.png"
                    filepath = os.path.join(IMAGE_DIR, filename)
                    
                    with open(filepath, "wb") as f:
                        f.write(image_data)
                    
                    print(f"画像を保存しました: {filepath}")
                    return filepath
                else:
                    print(f"レスポンスに画像データが含まれていませんでした: {result}")
            else:
                print(f"APIエラー ({endpoint['name']}): {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"画像生成中に例外が発生しました ({endpoint['name']}): {e}")
            import traceback
            traceback.print_exc()

    print("すべてのモデルで画像生成に失敗しました。")
    return None

if __name__ == "__main__":
    prompt = "A warm photograph of a craftsman-style wooden kitchen counter with a bowl of steaming ramen and a glass of beer at night. Soft pendant lighting. Film grain."
    generate_image(prompt)
