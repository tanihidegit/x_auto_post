import schedule
import time
import datetime
import os
import sys

# srcモジュールをインポート
from src.content_generator import generate_content
from src.image_generator import generate_image
from src.x_poster import post_tweet

def job():
    print(f"\n[{datetime.datetime.now()}] Job started.")
    
    # 1. コンテンツ生成
    print("コンテンツを生成中...")
    content = generate_content()
    if not content:
        print("コンテンツ生成に失敗しました。処理を中断します。")
        return

    tweet_text = content["tweet_text"]
    image_prompt = content["image_prompt"]
    print(f"生成されたテキスト: {tweet_text}")
    print(f"画像プロンプト: {image_prompt}")

    # 2. 画像生成
    print("画像を生成中...")
    image_path = generate_image(image_prompt)
    if not image_path:
        print("画像生成に失敗しました。処理を中断します。")
        return
    
    # 3. X投稿
    print("Xへ投稿中...")
    # 注意: 実際に投稿する場合はAPIキーが必要です。
    # APIキーが設定されていない場合やエラー時はここで失敗しますが、
    # 開発中は画像生成まで確認できればOKとします。
    success = post_tweet(tweet_text, image_path)
    
    if success:
        print("全ての処理が完了しました。")
        # 成功した場合、画像は x_poster.py 内で削除されています
    else:
        print("投稿に失敗しました。")
        # 失敗した場合、画像は残る可能性があります

def run_once():
    """
    即時実行用関数（テスト用）
    """
    print("即時実行モードで開始します...")
    job()

if __name__ == "__main__":
    # 引数チェック
    import argparse
    parser = argparse.ArgumentParser(description='X Auto Post System')
    parser.add_argument('--now', action='store_true', help='Run the job immediately once')
    args = parser.parse_args()

    if args.now:
        run_once()
        sys.exit()

    # スケジュール設定
    schedule_time = "19:00"
    schedule.every().day.at(schedule_time).do(job)
    
    print(f"スケジュール実行モードで開始しました。毎日 {schedule_time} に実行されます。")
    print("Ctrl+C で終了します。")
    
    while True:
        schedule.run_pending()
        time.sleep(60)
