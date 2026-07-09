# クラウド化手順（台本 → 動画生成）GitHub Actions版

台本 `scripts/<ep>.txt` を用意して実行すると、クラウド上で
VOICEVOX音声 → グラフ → Remotionレンダ まで走り、完成mp4をダウンロードできる（Mac不要）。

## 仕組み
`.github/workflows/render.yml` が以下を自動実行：
1. VOICEVOX(Dockerサービス)を起動
2. Python依存 / Chrome / 日本語フォントを用意
3. `check_assets` → `qa` → `tts` → `graph` → 素材配置
4. `remotion render` で mp4 生成
5. mp4 を「成果物(Artifacts)」としてアップロード（14日間DL可）

## 初回セットアップ（1回だけ）

### 1. Git LFS を入れる（重いmp4/pngを扱うため）
```bash
brew install git-lfs
cd ~/Desktop/fx-2ch
git init
git lfs install
```

### 2. package-lock を含めてコミット
```bash
git add .gitattributes .gitignore CLOUD.md SETUP.md qa_prompt.md script_prompt.md run.sh
git add build/ remotion/src/ remotion/package.json remotion/package-lock.json remotion/tsconfig.json
git add assets/ scripts/ .github/
git add remotion/public/irasutoya remotion/public/bg remotion/public/se   # LFS対象
git commit -m "init: 2chFX/ゴールド動画パイプライン"
```
> 重い背景(ocean/nature/grandfather)は `.gitignore` 済み（自動ローテ対象外）。使う場合のみ手動追加。

### 3. GitHub にリポジトリを作って push
```bash
# GitHubで空のプライベートrepoを作成後：
git remote add origin git@github.com:<あなたのユーザー>/fx-2ch.git
git branch -M main
git push -u origin main   # LFSのアップロードに数分かかる
```

## 使い方（動画を作るたび）
1. 台本を `scripts/ep03.txt` などで用意し、コミット＆push
   ```bash
   git add scripts/ep03.txt && git commit -m "ep03台本" && git push
   ```
2. GitHub の **Actions** タブ → **Render Episode** → **Run workflow**
3. `ep` に `ep03` と入力して実行
4. 完了後、実行画面下の **Artifacts** から mp4 をダウンロード

## 注意・チューニング
- **レンダ速度**：無料ランナーは2コアで、15分動画のレンダに 40〜90分ほどかかる場合あり（タイムアウトは180分に設定）。急ぐなら Remotion Lambda(AWS) への差し替えで数分に短縮可能。
- **VOICEVOXクレジット**：概要欄に `VOICEVOX:四国めたん/ずんだもん/…` を必ず記載（`upload.py` の説明文で自動付与）。
- **秘密情報**：`build/token.json` `client_secret.json` はコミットしない（.gitignore済み）。

## フル無人化：台本生成→レンダ 一気通貫（実装済み）

`.github/workflows/auto_episode.yml` が、**旬ネタ取得 → Claude Opus 4.8 で台本 → 機械QA(自動リライト) → VOICEVOX/グラフ → Remotionレンダ → 台本コミット → 完成mp4** までを無人で回す。

- **トリガー**：週1のスケジュール実行（毎週火 06:00 JST）。手動実行（Run workflow）で ep名・中心軸を任意指定も可。
- **毎日にしたい場合**：`auto_episode.yml` の cron を `"0 21 * * *"` に変更。
- **ep名**：未指定なら `ep<日付>`（例 ep20260709）で自動採番。日付の数字で背景動画ローテも回る。
- **台本の頭脳**：`build/generate_script.py`（Opus 4.8・adaptive thinking・effort high）。フォーマット/タグ/話者/IMG台帳は実ファイルから読むので常に同期。`scripts/ep02.txt` を合格手本(few-shot)として渡す。`build/qa.py` が通るまで最大3回リライト（15分尺・OP/ED・グラフ・コンプラ・可読性を自動チェック）。
- **旬ネタ**：`build/fetch_topics.py`。ikioi/find.5ch から best-effort で拾い、取れなければ**週替りエバーグリーン軸**（FX×ゴールド14本ローテ）に自動フォールバック（CIから5chが弾かれても必ず1本供給）。本文はコピーせず論点・空気感だけ借用。
- **生成台本はリポジトリにコミット**される（記録＆再現用。`permissions: contents: write`）。

### 事前セットアップ（1回だけ）：APIキーをSecretsに登録
GitHub → リポジトリ → **Settings → Secrets and variables → Actions → New repository secret**
- Name：`ANTHROPIC_API_KEY`
- Value：Anthropicコンソールで発行したAPIキー

> コスト目安：Opus 4.8 で15〜20分の台本1本＝出力8千字前後＋思考トークンで数十円規模。毎日運用ならSonnet 5への切替も検討可（`generate_script.py` の `MODEL` を `claude-sonnet-5` に）。

## この先の全自動化（残り）
- **自動投稿**：レンダ後に YouTube Data API で予約投稿するステップを追加（`YT_TOKEN` をGitHub Secretsに）。
- **Driveへ保存**：mp4をArtifactsではなくGoogle Driveへ出力（rclone＋サービスアカウント）。
