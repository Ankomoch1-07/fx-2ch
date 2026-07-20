"""
旬ネタ取得：台本の「参考テーマ」を out/topics.txt に書き出す。
- ベースは週替りのエバーグリーン軸（FX×ゴールド）ローテ（ISO週番号で回す＝必ず取れる）。
- 追加で ikioi.jp / find.5ch.io から今話題のスレタイを best-effort で拾えたら足す
  （CIのIPは弾かれることがあるので、失敗しても静かに無視してベースだけ使う）。
※スレ本文はコピーしない。論点・空気感・旬だけを借りてオリジナル化する前提の"参考"。
使い方: python3 build/fetch_topics.py   （out/topics.txt を生成）
"""
import os
import re
import datetime

os.makedirs("out", exist_ok=True)

# --- 週替りエバーグリーン軸（必ず1本は確実に供給される土台） ---------------
# ゴールド旬（最高値圏）を最低1本混ぜつつ、FX/ゴールドの定番論点を毎週ずらす。
ROTATION = [
    "ゴールド最高値圏｜今から純金積立は高値掴みか｜比率と時間分散で守る",
    "FX退場の共通点｜結局ロットと資金管理で全部説明つく",
    "有事の金｜株暴落局面で金はなぜ買われるか｜ポートフォリオの守り",
    "レバレッジの罠｜ハイレバ即退場｜証拠金と許容損失で見る痛み",
    "金 vs 株・オルカン｜攻めと守りの役割分担｜どっちも持て論",
    "スワップ・不労所得の誘惑｜持ち越しリスクと現実の利回り",
    "現物 vs 純金積立 vs 金ETF｜初心者はどれ｜手数料と保管の落とし穴",
    "損切りできない心理｜コツコツドカン｜ナンピン・マーチンの地獄",
    "中央銀行の金買い｜なぜ国が金に逃げるか｜個人が知っておく背景",
    "兼業vs専業・入金力｜人的資本とロット｜生活と両立する現実解",
    "ドル建て金と円建て金｜円安と金価格｜為替でブレる仕組み",
    "資産の何%を金で持つべきか｜年代別の目安｜守りの比率の決め方",
    "億り人の裏側｜生き残りの資金管理｜再現できる部分だけ真似る",
    "金の出口・利確・リバランス｜いつ売る｜比率を保つだけの運用",
]

# 中心軸は「既存台本の本数」で回す。実行ごとに必ず+1進むので、14軸を順に全部使い切り、
# 14本先まで同じネタは出ない（週番号だと同週の月水金が全部同じ／日付だと偶奇で半分しか使われない問題を回避）。
import glob
today = datetime.date.today()
n_scripts = len(glob.glob("scripts/*.txt"))
base = ROTATION[n_scripts % len(ROTATION)]

# --- best-effort で実データも拾う（失敗OK） --------------------------------
live = []
try:
    import requests
    HEAD = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}

    def grab_titles(url, pat, limit=8):
        r = requests.get(url, headers=HEAD, timeout=12)
        r.raise_for_status()
        found = re.findall(pat, r.text)
        out = []
        for t in found:
            t = re.sub(r"\s+", " ", t).strip()
            if 6 <= len(t) <= 60 and t not in out:
                out.append(t)
            if len(out) >= limit:
                break
        return out

    # find.5ch.io：金/為替/ゴールド関連の話題スレタイ（HTMLのタイトルらしき箇所を粗く抽出）
    for q in ("ゴールド", "金 積立", "ドル円"):
        try:
            live += grab_titles(
                f"https://find.5ch.io/search?q={requests.utils.quote(q)}",
                r'class="title"[^>]*>([^<]{6,60})</',
            )
        except Exception:
            pass
    # ikioi 市況2の勢い上位（スレタイらしき文字列を粗く抽出）
    try:
        live += grab_titles(
            "https://ikioi.jp/board/livemarket2",
            r'<a[^>]*href="/thread/[^"]+"[^>]*>([^<]{6,60})</a>',
        )
    except Exception:
        pass
except Exception:
    pass

# 重複除去
seen, live_uniq = set(), []
for t in live:
    if t not in seen:
        seen.add(t)
        live_uniq.append(t)

# --- 出力 ------------------------------------------------------------------
lines = [f"【今回の中心軸（{today.isoformat()}）】", base, ""]
if live_uniq:
    lines.append("【実在の旬スレタイ（参考・論点/空気感のみ借用。本文コピー禁止）】")
    lines += [f"- {t}" for t in live_uniq[:12]]
else:
    lines.append("（実データ取得なし：中心軸のみで生成）")

open("out/topics.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
print(f"\n-> out/topics.txt （中心軸=日付ローテ {today.isoformat()} / 実データ{len(live_uniq)}件）")
