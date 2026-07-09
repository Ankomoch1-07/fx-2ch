"""
台本の完全自動生成（Claude Opus 4.8）。
  out/topics.txt の「参考テーマ」→ Opus 4.8 で VOICEVOX に流せる台本を生成
  → scripts/<ep>.txt に保存 → 機械QA(qa.py)が通るまで最大N回リライト。
フォーマット・タグ・話者・IMG台帳は実ファイルから読むので常に同期する。
既存の合格作 scripts/ep02.txt を few-shot 手本として渡す。

使い方:
  python3 build/generate_script.py --ep ep20260709
  （ANTHROPIC_API_KEY が必要。--topic で中心軸を明示指定も可）
"""
import argparse
import json
import os
import re
import subprocess
import sys

import anthropic

MODEL = "claude-opus-4-8"
MAX_ATTEMPTS = 3
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def build_system():
    speakers = json.loads(read("build/speakers.json"))
    manifest = json.loads(read("assets/irasutoya.json"))
    keys = [a["key"] for a in manifest["assets"]]
    key_lines = "\n".join(f"  {a['key']} … {a['desc']}" for a in manifest["assets"])
    exemplar = read("scripts/ep02.txt")

    return f"""あなたは日本のYouTube「2ch お金スレ」系まとめ動画（FX・ゴールド版）の構成作家です。
実在の5chスレ本文は一切コピーせず、論点・空気感・旬だけを借りて完全オリジナルの創作台本を書きます。
これはフィクションのエンタメであり投資助言ではありません。以下を厳守します。

【コンプラ（絶対）】
- 「必ず勝てる/必ず儲かる/絶対儲かる/確実に儲かる/誰でも儲かる/元本保証/必ず上がる」等の断定・勧誘表現は禁止。
- 特定業者の推奨・具体的売買推奨はしない。損失やリスクを軽視しない（"生き残り"視点）。登場人物・体験談は全て架空。

【ターゲット】40代以上・投資初心者が「見たい」と思える台本。専門用語（ロット/ドルコスト/ETF/リバランス等）は必ず会話の中で噛み砕く。下品・過度な煽りは避け、家計・老後・お金の不安といった生活実感に寄り添う。難しくなったら新人ニキの素朴な質問で受け止める。

【尺（必須）】本文の日本語で6,000〜8,000字（=約15〜20分）。**必ず15分を超える**こと。足りなければレスとサブ論点（税金・手数料・業者比較・他資産比較・年代別の目安・「いくら持ってる」晒し合い等）を足す。

【登場人物＝VOICEVOX話者（この名前だけを【】に使う。他の名前は禁止）】
- 四国めたん … ナレーター（丁寧語・落ち着き）。冒頭/解説/結びを担当。
- ずんだもん … ワイ（自虐・失敗担当・視聴者の代弁、一人称ワイ/俺）
- 玄野武宏 … 先輩（ベテラン・断言役）
- 青山龍星 … 逆張りニキ（攻めろ論・contrarian）
- 九州そら … 冷静ニキ（数字と理屈で諭す）
- 春日部つむぎ … 新人ニキ（素朴な質問役／混乱・「全然わからん」担当）
- No.7 … 養分ニキ（否定・諦め・自虐の煽られ役／「どうせ養分」系。たまに手のひら返し）

【2ちゃんねらーらしさ】ｗｗｗ/草/それな/わかる/ほんまか？/情弱/エアプ/にわか/養分/手のひら返し 等を自然に散らす（1〜2レスに1回程度、多用しすぎない＝40代初心者向け）。全員が同意しないのが2ch。否定・諦め・混乱・共感・煽り合い・自虐・手のひら返しの感情の幅を、養分ニキと新人ニキで作る。関西弁ベース、テンポ重視、1レス1〜4文。掛け合いブロックは各8〜14レスで厚めに。

【特殊タグ（この形式のみ。ト書き・マークダウン装飾は書かない）】
- 発話：`【話者名】セリフ` を1行1発話。
- 冒頭の演出（この順で必ず）：
    [OP_HOOK]
    【四国めたん】今回ご紹介するスレッドはこちら。
    [OP_TITLE]
    [OPIMG: key, key, key]   ← 関連いらすとやkey×3
    【四国めたん】（スレタイを1文で読み上げ）
    [OP_DESC]
    【四国めたん】（スレ内容の説明〜「それでは早速見ていきましょう」まで、1発話で長め）
- 結びの演出：
    [ED]
    [EDIMG: key, key, key]   ← お祝い/前向き系key×3
    【四国めたん】（結論＋コメント誘導＋チャンネル登録/高評価/スーパーサンクス＋ご視聴ありがとう、1発話で長め）
- グラフ（解説の直前に1行）：`[GRAPH: タイトル | ラベル:数値, ラベル:数値 | Y軸ラベル]`
    直後は必ず【四国めたん】の解説を置き、数値には [要ファクトチェック] を付ける。グラフごとに別データにする。最低2枚。
- 画像：場面の雰囲気が変わる所ごとに `[IMG:key]` を1行（sticky＝次の[IMG:]まで継続、レス3つに最低1回は変える）。narratorには不要。
- 数字を出したら直後に [要ファクトチェック]。ショートの山場の前に [SHORT候補]。

【[IMG:key] / [OPIMG] / [EDIMG] で使えるkey（この一覧のkeyだけ。存在しないkeyは絶対に作らない）】
{key_lines}

【1行目】必ず `# 【2chFXスレ】…【2ch有益スレ】` 形式の動画タイトル（32字前後、煽りすぎない）。ゴールド回なら【2chゴールドスレ】でも可。

以下は「合格済みの手本（この作風・粒度・タグ運用を厳守）」です。丸写しはせず、テーマに合わせて新規に書き切ってください。
=== 手本ここから ===
{exemplar}
=== 手本ここまで ===

出力は台本本文のみ（説明文・前置き・```などのコードフェンスは一切不要）。1行目の # タイトルから最後の結びまで、全文を書き切ること。"""


def build_user(topics, prev=None, warnings=None):
    if prev and warnings:
        return (f"以下の【参考テーマ】から1本、完全オリジナルの台本を作ってください。\n\n"
                f"【参考テーマ】\n{topics}\n\n"
                f"直前に書いた台本が機械QAで下記の指摘を受けました。**全ての指摘を解消**し、"
                f"フォーマット・タグ・話者・尺(15分超)・コンプラを守ったまま、台本の全文を最初から書き直してください。\n\n"
                f"【QA指摘】\n{warnings}\n\n"
                f"【直前の台本（参考。改善して置き換える）】\n{prev}")
    return (f"以下の【参考テーマ】から最もフックの強い切り口を1本選び、"
            f"完全オリジナルの台本を全文書いてください（1行目の#タイトルから結びまで）。\n\n"
            f"【参考テーマ】\n{topics}\n")


def generate(client, system, user):
    with client.messages.stream(
        model=MODEL,
        max_tokens=32000,
        thinking={"type": "adaptive"},
        output_config={"effort": "high"},
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        sys.exit("Claudeが生成を拒否しました（stop_reason=refusal）。テーマを見直してください。")
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def sanitize(text):
    """コードフェンス除去・不正な[IMG:key]行の削除・タイトル行の担保。"""
    text = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", text.strip())
    valid = {a["key"] for a in json.loads(read("assets/irasutoya.json"))["assets"]}
    out, dropped = [], []
    for ln in text.splitlines():
        m = re.match(r"\s*\[IMG:\s*([\w-]+)\s*\]\s*$", ln)
        if m and m.group(1) not in valid:
            dropped.append(m.group(1))
            continue                      # 未知keyのIMG行は落とす（stickyなので直前画像が継続）
        out.append(ln.rstrip())
    if dropped:
        print(f"  ! 未知IMG keyを{len(dropped)}行削除: {sorted(set(dropped))}")
    # 先頭が # でなければタイトル行を補う（保険）
    body = "\n".join(out).strip()
    if not body.lstrip().startswith("#"):
        body = "# 【2chFXスレ】お金の話【2ch有益スレ】\n" + body
    return body + "\n"


def run_qa(path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, "build/qa.py"), path],
                       capture_output=True, text=True)
    warnings = [l.strip()[1:].strip() for l in r.stdout.splitlines() if l.strip().startswith("⚠")]
    return r.returncode == 0, warnings, r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True, help="エピソード名（scripts/<ep>.txt）")
    ap.add_argument("--topic", default=None, help="中心軸を明示指定（省略時 out/topics.txt）")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out_path = args.out or os.path.join(ROOT, "scripts", f"{args.ep}.txt")
    if args.topic:
        topics = args.topic
    elif os.path.exists(os.path.join(ROOT, "out/topics.txt")):
        topics = read("out/topics.txt")
    else:
        topics = "ゴールド最高値圏｜今から純金積立は高値掴みか｜比率と時間分散で守る"

    client = anthropic.Anthropic()
    system = build_system()

    best_text, best_warn, prev, warns_text = None, 999, None, None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"=== 生成 試行 {attempt}/{MAX_ATTEMPTS}（{MODEL}）===")
        text = sanitize(generate(client, system, build_user(topics, prev, warns_text)))
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        passed, warnings, report = run_qa(out_path)
        print(report)
        if len(warnings) < best_warn:
            best_text, best_warn = text, len(warnings)
        if passed:
            print(f"✓ QA全通過（{out_path}）")
            return
        print(f"⚠ QA {len(warnings)}件 → リライト")
        prev, warns_text = text, "\n".join(f"- {w}" for w in warnings)

    # 全試行でwarningが残っても、一番良かった版を残してレンダは続行させる
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(best_text)
    print(f"△ QA警告 残り{best_warn}件だが最良版を採用（{out_path}）。レンダは続行。")


if __name__ == "__main__":
    main()
