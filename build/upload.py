"""
完成mp4をYouTubeに限定→予約公開でアップロード。
初回のみ build/client_secret.json を用意（Google Cloud OAuthクライアント/デスクトップ）。
使い方:
  python3 build/upload.py out/ep01.mp4 "タイトル" "説明文" "2026-07-10T01:15:00Z"
  ※publish_at は ISO8601 UTC（JST -9h）
"""
import sys, os
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.http
import google.oauth2.credentials as oc

SC = ["https://www.googleapis.com/auth/youtube.upload"]
DISCLAIMER = "\n\n※本動画はフィクションであり、特定の投資を推奨するものではありません。投資は自己責任で。"


def creds():
    if os.path.exists("build/token.json"):
        return oc.Credentials.from_authorized_user_file("build/token.json", SC)
    fl = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
        "build/client_secret.json", SC)
    cr = fl.run_local_server(port=0)
    open("build/token.json", "w").write(cr.to_json())
    return cr


def main():
    mp4, title, desc, publish_at = sys.argv[1:5]
    yt = googleapiclient.discovery.build("youtube", "v3", credentials=creds())
    body = {
        "snippet": {"title": title, "description": desc + DISCLAIMER, "categoryId": "25"},
        "status": {"privacyStatus": "private", "publishAt": publish_at,
                   "selfDeclaredMadeForKids": False},
    }
    req = yt.videos().insert(
        part="snippet,status", body=body,
        media_body=googleapiclient.http.MediaFileUpload(mp4, chunksize=-1, resumable=True))
    r = req.execute()
    print("uploaded:", r["id"], "publishAt:", publish_at)


if __name__ == "__main__":
    main()
