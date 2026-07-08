"""
台本の機械QA：ターゲット（40代以上・投資初心者・見たいと思えるか）に向けた
尺・構成・コンプラ・可読性の自動チェック。レンダ前ゲート。
使い方: python3 build/qa.py scripts/ep02.txt
"""
import sys, re

lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
text = "\n".join(lines)
segs = [l for l in lines if l.startswith("【")]
def body(l): return re.sub(r"【.+?】|\[.*?\]", "", l).strip()
chars = sum(len(body(l)) for l in segs)
# 実測補正：発話 約370字/分 ＋ 各発話後の無音0.35秒ぶんを加算
est_min = chars / 370.0 + len(segs) * 0.35 / 60.0

ok, warn = [], []
def check(cond, good, bad):
    (ok if cond else warn).append(good if cond else bad)

# 尺（15分以上・必須）
check(est_min >= 15,
      f"尺 約{est_min:.1f}分（本文{chars}字）",
      f"尺 約{est_min:.1f}分（本文{chars}字）← 15分未満。レス/論点を追加")

# OP/ED 構成
for mk, label in [("[OP_HOOK]", "OPフック"), ("[OP_TITLE]", "OPタイトル"),
                  ("[OP_DESC]", "OP説明"), ("[ED]", "ED")]:
    check(mk in text, f"{label} あり", f"{label} 無し ← 追加")

# グラフ（構造化）
graphs = [l for l in lines if l.strip().startswith("[GRAPH")]
check(bool(graphs) and all("|" in g for g in graphs),
      f"グラフ {len(graphs)}枚・構造化OK",
      "グラフ未設定 or 旧式 ← [GRAPH: タイトル | ラベル:値 | Y軸] に")

# 数字の裏取りタグ
check("[要ファクトチェック]" in text,
      "要ファクトチェック あり", "要ファクトチェック 無し ← 数字に付与")

# コンプラ：断定・投資勧誘の禁止表現
banned = [p for p in ["必ず勝", "必ず儲", "絶対儲", "絶対に勝", "確実に儲",
                      "確実に勝", "誰でも儲か", "元本保証", "必ず上がる"] if p in text]
check(not banned, "禁止表現 なし", f"禁止表現 検出: {banned} ← 要修正")

# 可読性：長すぎるレス（吹き出しはみ出し・初心者に読みにくい）※ナレーターは除外
longs = [l for l in segs if not l.startswith("【四国めたん】") and len(body(l)) > 95]
check(not longs, "長すぎるレス なし（95字以内）",
      f"長すぎるレス {len(longs)}件（95字超）← 2つに分割推奨")

# スラング密度（40代初心者向け：出しすぎ注意）
slang = len(re.findall(r"ｗ|草|養分|情強|情弱|エアプ|にわか|ポジトーク", text))
ratio = slang / max(1, len(segs))
check(ratio <= 0.8, f"スラング密度 {ratio:.2f}/レス（適正）",
      f"スラング密度 {ratio:.2f}/レス ← やや多い。40代初心者向けに抑えめ推奨")

print(f"=== 機械QA: {sys.argv[1]} ===")
for o in ok:   print("  ✓", o)
for w in warn: print("  ⚠", w)
print(f"\n判定: {'PASS（機械チェックは全通過）' if not warn else str(len(warn)) + '件 要確認'}")
sys.exit(1 if warn else 0)
