"""
完成mp4を YouTube に自動アップロード（既定=非公開private）。
- 認証はOAuthのリフレッシュトークン方式（GitHub Secrets: YT_CLIENT_ID / YT_CLIENT_SECRET / YT_REFRESH_TOKEN）。
- Secretsが未設定なら何もせずスキップ（パイプラインは止めない）。
- タイトル＝台本の#行、概要欄＝免責＋VOICEVOXクレジット入りテンプレを自動生成。
- サムネは手動運用のため、非公開でアップ→人がサムネ付与＋公開する想定。
使い方: python3 build/upload_youtube.py --ep ep20260724
"""
import argparse
import os

TAGS = ["2ch", "なんJ", "FX", "ゴールド", "投資", "お金", "資産運用", "新NISA"]

DESC = """【今回のスレ】{title}

2ch民がお金・投資について本音でバトル。初心者にも分かるように噛み砕いて解説します。

━━━━━━━━━━━━━━
▼ 免責事項（必ずお読みください）
本動画はエンターテインメントを目的としたフィクションです。登場人物・体験談はすべて架空であり、
特定の金融商品の売買を推奨・勧誘するものではありません。投資は元本割れのリスクを伴います。
最終的な投資判断はご自身の責任でお願いします。

▼ クレジット
音声：VOICEVOX（四国めたん／ずんだもん／玄野武宏／青山龍星／九州そら／春日部つむぎ／No.7）
イラスト：いらすとや https://www.irasutoya.com/

▼ チャンネル登録・高評価・スーパーサンクスで応援よろしくお願いします！

#2ch #なんJ #FX #ゴールド #投資 #お金 #資産運用 #新NISA
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--file", default=None, help="mp4パス（既定 out/<ep>.mp4）")
    args = ap.parse_args()

    cid = os.environ.get("YT_CLIENT_ID")
    csec = os.environ.get("YT_CLIENT_SECRET")
    rtok = os.environ.get("YT_REFRESH_TOKEN")
    if not (cid and csec and rtok):
        print("YT_CLIENT_ID/SECRET/REFRESH_TOKEN 未設定 → YouTubeアップロードをスキップ")
        return

    mp4 = args.file or os.path.join("out", f"{args.ep}.mp4")
    if not os.path.exists(mp4):
        print(f"mp4が見つかりません: {mp4} → スキップ")
        return

    # タイトル＝台本の#行
    title = args.ep
    sp = os.path.join("scripts", f"{args.ep}.txt")
    if os.path.exists(sp):
        for ln in open(sp, encoding="utf-8"):
            if ln.strip().startswith("#"):
                title = ln.lstrip("# ").strip()
                break

    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials(None, refresh_token=rtok, client_id=cid, client_secret=csec,
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    creds.refresh(Request())
    yt = build("youtube", "v3", credentials=creds)

    privacy = os.environ.get("YT_PRIVACY", "private")
    body = {
        "snippet": {"title": title[:100], "description": DESC.format(title=title)[:4900],
                    "tags": TAGS, "categoryId": "22"},   # 22 = People & Blogs
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    media = MediaFileUpload(mp4, chunksize=8 * 1024 * 1024, resumable=True, mimetype="video/mp4")
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    print(f"アップロード開始: {mp4}（{privacy}）")
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"  {int(status.progress() * 100)}%")
    vid = resp["id"]
    print(f"done: https://youtu.be/{vid} （{privacy}）")
    print("→ YouTube Studioでサムネを設定し、内容を確認して公開してください。")


if __name__ == "__main__":
    main()
