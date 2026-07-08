#!/bin/bash
# 使い方: ./run.sh ep01
# 前提: VOICEVOX(Docker)が :50021 で起動中 / remotion/ は npm i 済み
set -e
EP=$1
[ -z "$EP" ] && { echo "usage: ./run.sh <ep-name>"; exit 1; }

echo "▶ 0/4 素材チェック＋台本QA"
python3 build/check_assets.py "scripts/$EP.txt"
python3 build/qa.py "scripts/$EP.txt" || echo "  （QA警告あり。確認のうえ続行）"
echo "▶ 1/4 音声＋タイムライン生成"
python3 build/tts.py   "scripts/$EP.txt"
echo "▶ 2/4 解説グラフ生成"
python3 build/graph.py "scripts/$EP.txt"

echo "▶ 3/4 素材をRemotionのpublicへ配置"
DEST="remotion/public/$EP"
mkdir -p "$DEST/graph"
cp out/voice.wav       "$DEST/voice.wav"
cp out/timeline.json   "$DEST/timeline.json"
cp out/graph/*.png     "$DEST/graph/" 2>/dev/null || true
# 立ち絵は初回に remotion/public/chara/<話者名>.png を用意しておく（使い回し）

echo "▶ 4/4 Remotionレンダ → out/$EP.mp4"
( cd remotion && npx remotion render src/index.ts Main "../out/$EP.mp4" \
    --props="{\"ep\":\"$EP\"}" )

echo "✅ 完成: out/$EP.mp4"
echo "   → タイトル/サムネ/冒頭30秒を確認し build/upload.py で予約投稿"
