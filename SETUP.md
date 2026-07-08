# 2chFXスレ 自動化パイプライン 構築手順書 v1 (macOS)

台本(話者タグ付き) → 音声 → グラフ → 動画 → YouTube予約投稿 を1コマンドで回す。
MVPは「1本を手元でレンダして限定公開に上げる」まで。慣れたら全自動化。

推奨ディレクトリ構成：
```
fx-2ch/
├─ prompts/            # script_prompt.md（既出の量産プロンプト）
├─ scripts/            # ①LLM出力の台本 .txt をここに置く
├─ build/
│   ├─ tts.py          # VOICEVOX音声化
│   ├─ graph.py        # [GRAPH:] を画像化
│   └─ upload.py       # YouTube投稿
├─ remotion/           # 映像組立（Remotionプロジェクト）
└─ out/                # 完成mp4・素材
```

---

## Phase 0 ── 前提ツール（初回のみ）

```bash
# Homebrew前提。無ければ https://brew.sh
brew install node python@3.12 ffmpeg
# Docker Desktop（VOICEVOX ENGINE用） https://www.docker.com/products/docker-desktop/
python3 -m pip install requests matplotlib japanize-matplotlib google-api-python-client google-auth-oauthlib
```

---

## Phase 1 ── VOICEVOX で音声化

### 1-1. エンジン起動（Dockerで常駐、無料）
```bash
docker run -d --name voicevox -p 50021:50021 voicevox/voicevox_engine:cpu-latest
# 確認： curl http://localhost:50021/speakers | head
```

### 1-2. 話者ID対応表（build/speakers.json）
※ `curl http://localhost:50021/speakers` で実IDを確認して埋める（下は代表値の例）
```json
{
  "四国めたん": 2,
  "ずんだもん": 3,
  "玄野武宏": 11,
  "青山龍星": 13,
  "九州そら": 16,
  "春日部つむぎ": 8
}
```

### 1-3. build/tts.py（台本→wav結合。タグは字幕用に別ファイルへ）
```python
import sys, re, json, subprocess, requests, os
ENG="http://localhost:50021"
spk=json.load(open("build/speakers.json"))
lines=open(sys.argv[1],encoding="utf-8").read().splitlines()
os.makedirs("out/wav",exist_ok=True); parts=[]; subs=[]
i=0
for ln in lines:
    m=re.match(r"【(.+?)】(.+)", ln)
    if not m: continue                      # #タイトルや[GRAPH]等はスキップ
    name,txt=m.group(1),m.group(2)
    txt=re.sub(r"\[.*?\]","",txt).strip()   # [要ファクトチェック]等を除去
    if not txt: continue
    sid=spk.get(name,3)
    q=requests.post(f"{ENG}/audio_query",params={"text":txt,"speaker":sid}).json()
    q["speedScale"]=1.05                     # ゆっくりめ。好みで調整
    wav=requests.post(f"{ENG}/synthesis",params={"speaker":sid},json=q).content
    p=f"out/wav/{i:04d}.wav"; open(p,"wb").write(wav); parts.append(p)
    subs.append(f"{name}\t{txt}"); i+=1
# 無音0.35秒を挟んで結合
with open("out/list.txt","w") as f:
    for p in parts: f.write(f"file '{os.path.abspath(p)}'\n")
subprocess.run(["ffmpeg","-y","-f","concat","-safe","0","-i","out/list.txt",
                "-af","apad=pad_dur=0.35","out/voice.wav"])
open("out/subs.tsv","w",encoding="utf-8").write("\n".join(subs))
print("done: out/voice.wav / out/subs.tsv")
```
```bash
python3 build/tts.py scripts/ep01.txt
```

---

## Phase 2 ── [GRAPH:] を自動で画像化

### build/graph.py（台本から [GRAPH:] 行を拾ってPNG生成）
```python
import re, sys, matplotlib.pyplot as plt, japanize_matplotlib, os
os.makedirs("out/graph",exist_ok=True)
cues=[l for l in open(sys.argv[1],encoding="utf-8") if l.strip().startswith("[GRAPH")]
# MVP: 定番グラフを固定テンプレで用意（内容はcueテキストでLLMに係数を出させてもよい）
for idx,c in enumerate(cues):
    fig,ax=plt.subplots(figsize=(16,9),dpi=120)
    x=["2%リスク","10%リスク"]; y=[67,44]           # 例。cueに応じ差し替え
    ax.bar(x,y,color=["#2e7d32","#c62828"])
    ax.set_title(re.sub(r"\[GRAPH:?","",c).strip("] \n"),fontsize=28)
    ax.set_ylabel("20連敗後の資金残存率(%)",fontsize=20)
    for i,v in enumerate(y): ax.text(i,v+1,f"{v}%",ha="center",fontsize=24)
    fig.savefig(f"out/graph/{idx:02d}.png",bbox_inches="tight"); plt.close()
print(f"{len(cues)} graphs")
```
> 発展：cueの数値もLLMに出させ `[GRAPH: x=..., y=...]` 形式にすれば完全自動。

---

## Phase 3 ── Remotion で映像組立（2ch掲示板UI＋字幕＋立ち絵）

### 3-1. 初期化
```bash
cd fx-2ch && npm create video@latest remotion   # Blank を選択
cd remotion && npm i
```

### 3-2. 発想（最小構成）
- `out/voice.wav` を `<Audio>` で敷く。総尺 = 音声長。
- `out/subs.tsv` を読み、1発話=数秒の連続シーケンスとして下部にレス吹き出しを積む（自動スクロール）。
- 話者ごとに立ち絵PNG（`public/chara/ずんだもん.png` 等）を左右に出し分け。
- `[GRAPH]` タイミングで `out/graph/xx.png` を全画面差し込み。
- 背景は掲示板風の薄いテンプレ（`public/bg.png`）。

### 3-3. 字幕→シーケンス化の考え方（src/Video.tsx 抜粋イメージ）
```tsx
// subs.tsv と各wavのdurationから開始フレームを積算し、
// <Sequence from={start} durationInFrames={len}> に <Bubble name text/> を並べる。
// 立ち絵は name で public/chara/${name}.png を出す。
// GRAPH行は <Img src={graph}/> を全画面で被せる。
```
> ここはテンプレ固定の作り込みが一度必要（初回のみ）。以降は素材を差し替えるだけで量産。

### 3-4. レンダ
```bash
npx remotion render src/index.ts Main ../out/video_raw.mp4 --props='{"ep":"ep01"}'
```

---

## Phase 4 ── 最終合成（保険。Remotionが音声込みならスキップ可）
```bash
ffmpeg -y -i out/video_raw.mp4 -i out/voice.wav -c:v copy -c:a aac -shortest out/ep01.mp4
```

---

## Phase 5 ── YouTube 予約投稿（API）

### 5-1. 準備（初回のみ）
1. Google Cloud Consoleでプロジェクト作成 → **YouTube Data API v3** を有効化
2. OAuth同意画面＋OAuthクライアントID(デスクトップ)を作成 → `client_secret.json` を build/ に置く
3. 初回実行でブラウザ認証 → `token.json` が保存され以降無人

### 5-2. build/upload.py
```python
import sys, os
import google_auth_oauthlib.flow, googleapiclient.discovery, googleapiclient.http
import google.oauth2.credentials as oc
SC=["https://www.googleapis.com/auth/youtube.upload"]
def creds():
    if os.path.exists("build/token.json"):
        return oc.Credentials.from_authorized_user_file("build/token.json",SC)
    fl=google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file("build/client_secret.json",SC)
    cr=fl.run_local_server(port=0); open("build/token.json","w").write(cr.to_json()); return cr
yt=googleapiclient.discovery.build("youtube","v3",credentials=creds())
mp4,title,desc,publish_at=sys.argv[1],sys.argv[2],sys.argv[3],sys.argv[4] # publish_at: ISO8601 UTC
body={"snippet":{"title":title,"description":desc,"categoryId":"25"},
      "status":{"privacyStatus":"private","publishAt":publish_at,"selfDeclaredMadeForKids":False}}
req=yt.videos().insert(part="snippet,status",body=body,
     media_body=googleapiclient.http.MediaFileUpload(mp4,chunksize=-1,resumable=True))
r=req.execute(); print("uploaded:",r["id"])
```
```bash
# 例：2026-07-10 10:15 JST(=01:15 UTC)に予約公開
python3 build/upload.py out/ep01.mp4 "【2chFXスレ】…【2ch有益スレ】" "説明文…" "2026-07-10T01:15:00Z"
```
> ⚠ 概要欄に「本動画はフィクションであり投資助言ではありません」を必ず定型で入れる。

---

## Phase 6 ── オーケストレーション（1コマンド化）

### run.sh
```bash
#!/bin/bash
set -e
EP=$1                                   # 例: ep01
python3 build/tts.py   scripts/$EP.txt
python3 build/graph.py scripts/$EP.txt
( cd remotion && npx remotion render src/index.ts Main ../out/video_raw.mp4 --props="{\"ep\":\"$EP\"}" )
ffmpeg -y -i out/video_raw.mp4 -i out/voice.wav -c:v copy -c:a aac -shortest out/$EP.mp4
echo "完成: out/$EP.mp4 （タイトル/サムネ/冒頭30秒を確認 → upload.pyで予約）"
```
```bash
chmod +x run.sh && ./run.sh ep01
```

---

## 完成後の全自動ループ（将来）
1. cron/GitHub Actions で ①ネタ→②タイトル→③台本 をLLM APIで生成し `scripts/` に保存
2. `[要ファクトチェック]` を含む台本だけSlack等へ通知（人が数字確認）
3. `run.sh` 実行 → `upload.py` で予約投稿（長尺→数時間後④ショート）
4. vidIQ `score_title`/`score_thumbnail` を組み込み、低スコアは再生成

## 構築順の推奨
Phase1（音声）→ Phase2（グラフ）→ Phase5（投稿）を先に通し、
最後にPhase3（Remotion映像）を作り込むと、各段を単体で検証しやすい。
映像は初回のテンプレ作成だけが山場。そこを越えれば以降は素材差し替えで量産。
