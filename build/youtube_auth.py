"""
【ローカルで1回だけ実行】YouTube投稿用のリフレッシュトークンを取得する。
事前準備:
  1) Google Cloudでプロジェクト作成 → 「YouTube Data API v3」を有効化
  2) 「OAuth同意画面」を設定（ユーザー種別=外部、テスト ユーザーに自分のGoogleアカウントを追加）
  3) 認証情報 → OAuthクライアントID → アプリの種類「デスクトップ」→ JSONをダウンロードし
     このファイルと同じ場所に client_secret.json という名前で置く
実行:
  pip install google-auth-oauthlib
  python3 build/youtube_auth.py            （ブラウザが開くので自分のアカウントで許可）
出力された YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN を GitHub Secrets に登録する。
"""
import sys
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

secret_file = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
flow = InstalledAppFlow.from_client_secrets_file(secret_file, SCOPES)
# access_type=offline + prompt=consent でリフレッシュトークンを確実に取得
creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

# トークンは秘密なので画面には出さず、gitignore済みの yt_secrets.txt に保存
out = (f"YT_CLIENT_ID={creds.client_id}\n"
       f"YT_CLIENT_SECRET={creds.client_secret}\n"
       f"YT_REFRESH_TOKEN={creds.refresh_token}\n")
open("yt_secrets.txt", "w").write(out)
print("\n認証に成功しました！ 3つの値を yt_secrets.txt に保存しました。")
print("→ このファイルを開き、YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN を GitHub Secrets に登録してください。")
if not creds.refresh_token:
    print("※refresh_tokenが空でした：Googleアカウントのアプリ連携を一度解除してから再実行してください。")
