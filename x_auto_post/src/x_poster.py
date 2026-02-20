import os
import tweepy
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# APIキーの設定
consumer_key = os.getenv("X_API_KEY")
consumer_secret = os.getenv("X_API_SECRET")
access_token = os.getenv("X_ACCESS_TOKEN")
access_token_secret = os.getenv("X_ACCESS_TOKEN_SECRET")
bearer_token = os.getenv("X_BEARER_TOKEN")

def get_twitter_conn_v1(api_key, api_secret, access_token, access_token_secret):
    """
    API v1.1 認証 (メディアアップロード用)
    """
    auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_token_secret)
    return tweepy.API(auth)

def get_twitter_conn_v2(api_key, api_secret, access_token, access_token_secret):
    """
    API v2 認証 (ツイート投稿用)
    """
    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_token_secret,
    )
    return client

def post_tweet(text, image_path):
    """
    画像をアップロードし、テキストと共にXに投稿します。
    """
    # キーのチェック
    if not all([consumer_key, consumer_secret, access_token, access_token_secret]):
        print("X APIキーが設定されていません。.envファイルを確認してください。")
        return False

    try:
        # API v1.1 インスタンス作成 (画像アップロード)
        api_v1 = get_twitter_conn_v1(consumer_key, consumer_secret, access_token, access_token_secret)
        
        # 画像アップロード
        media = api_v1.media_upload(filename=image_path)
        media_id = media.media_id
        print(f"画像アップロード成功 (Media ID: {media_id})")

        # API v2 インスタンス作成 (投稿)
        client_v2 = get_twitter_conn_v2(consumer_key, consumer_secret, access_token, access_token_secret)
        
        # ツイート投稿
        response = client_v2.create_tweet(text=text, media_ids=[media_id])
        print(f"投稿成功: https://twitter.com/user/status/{response.data['id']}")
        
        # 投稿後に画像を削除
        if os.path.exists(image_path):
            os.remove(image_path)
            print("一時画像を削除しました。")
            
        return True

    except Exception as e:
        print(f"Xへの投稿中にエラーが発生しました: {e}")
        return False

if __name__ == "__main__":
    # テスト実行には有効なAPIキーと画像パスが必要です
    pass
