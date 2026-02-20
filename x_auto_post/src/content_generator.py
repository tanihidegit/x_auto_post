import os
import json
import google.generativeai as genai
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# APIキーの設定
api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError("GOOGLE_API_KEYが設定されていません。.envファイルを確認してください。")

genai.configure(api_key=api_key)

def generate_content():
    """
    Gemini APIを使用して、X投稿用のテキストと画像プロンプトを生成します。
    """
    # 使用するモデル (JSONモード対応)
    model_name = "gemini-2.0-flash"
    
    generation_config = {
        "temperature": 0.7,
        "top_p": 0.95,
        "top_k": 64,
        "max_output_tokens": 8192,
        # "response_mime_type": "application/json",
    }

    model = genai.GenerativeModel(
        model_name=model_name,
        generation_config=generation_config,
        system_instruction="""
あなたは「建築/設計/現場」のプロで「グルメ」を愛する40代です。
以下の要件で、Xの投稿本文と、それに添付する画像の生成用プロンプトを作成してください。

【出力フォーマット（JSON形式で返すこと）】
{
  "tweet_text": "ここに5・7・5を1行目に入れた投稿本文（ハッシュタグ込み）",
  "image_prompt": "ここに画像生成AIに渡すための、具体的で情緒的な描写の画像生成指示文（英語推奨）"
}

【コンテンツの要件】
・テーマ：「空間設計（間取り、素材、照明、現場の納まり等）」×「グルメ（味噌汁、晩酌、手料理等）」の融合。
・タイトル（本文1行目）：必ずテーマに沿った「5・7・5」（川柳風）のキャッチコピーにすること。
・ターゲット・トーン：40代以上の大人が共感する、落ち着いたプロ目線の情緒的な文章。
・画像プロンプトの要件：写真としてリアルで、美しい光の描写を含むこと。（例: A warm photograph of a craftsman-style wooden kitchen counter with a bowl of steaming ramen and a glass of beer at night. Soft pendant lighting. Film grain.）
"""
    )

    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content("投稿内容を生成してください。")
            
            # Markdownのコードブロックを削除
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

            # JSONレスポンスのパース
            content_json = json.loads(text)
            
            # 必須キーの確認
            if "tweet_text" not in content_json or "image_prompt" not in content_json:
                raise ValueError("APIからの応答に必要なキーが含まれていません。")
                
            return content_json

        except Exception as e:
            print(f"コンテンツ生成中にエラーが発生しました (試行 {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(5)  # 5秒待機
            else:
                import traceback
                traceback.print_exc()
                return None
        


if __name__ == "__main__":
    # テスト実行
    result = generate_content()
    if result:
        print("生成されたテキスト:", result["tweet_text"])
        print("生成された画像プロンプト:", result["image_prompt"])
