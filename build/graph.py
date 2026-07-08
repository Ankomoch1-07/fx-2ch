"""
台本の [GRAPH: タイトル | ラベル:値, ラベル:値, ... | Y軸ラベル] を解析し、
グラフごとに正しい棒グラフPNGを out/graph/NN.png に出力する。
旧式（データ無し）の [GRAPH: 説明] はフォールバックで簡易表示。
使い方: python3 build/graph.py scripts/ep01.txt
"""
import re, sys, os
import matplotlib
matplotlib.use("Agg")
try:
    import japanize_matplotlib  # noqa: F401  日本語フォント（ローカルMac等）
except Exception:
    # japanize_matplotlibが使えない環境（例: Python3.12でdistutils無し）は
    # システムの日本語フォントにフォールバック（CIはfonts-noto-cjkを導入済み）
    matplotlib.rcParams["font.family"] = [
        "Noto Sans CJK JP", "IPAexGothic", "Hiragino Sans", "TakaoPGothic", "sans-serif"]
import matplotlib.pyplot as plt

os.makedirs("out/graph", exist_ok=True)
cues = [l.strip() for l in open(sys.argv[1], encoding="utf-8") if l.strip().startswith("[GRAPH")]


def parse(cue):
    body = re.sub(r"^\[GRAPH:?", "", cue).strip().rstrip("]").strip()
    parts = [p.strip() for p in body.split("|")]
    title = parts[0] if parts else ""
    labels, values = [], []
    if len(parts) >= 2:
        for pair in parts[1].split(","):
            if ":" in pair:
                k, v = pair.rsplit(":", 1)
                labels.append(k.strip())
                try:
                    values.append(float(re.sub(r"[^0-9.\-]", "", v)))
                except ValueError:
                    values.append(0.0)
    ylabel = parts[2] if len(parts) >= 3 else ""
    return title, labels, values, ylabel


for idx, c in enumerate(cues):
    title, labels, values, ylabel = parse(c)
    if not labels:                              # データ未指定のフォールバック
        labels, values, ylabel = ["データA", "データB"], [50, 50], ""
    fig, ax = plt.subplots(figsize=(16, 9), dpi=120)
    colors = ["#2e7d32"] + ["#c62828"] * (len(labels) - 1)   # 先頭=緑, 以降=赤
    ax.bar(labels, values, color=colors[:len(labels)])
    ax.set_title(title, fontsize=30, pad=20)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=22)
    top = max(values) if values else 100
    ax.set_ylim(0, top * 1.25)
    for i, v in enumerate(values):
        ax.text(i, v + top * 0.02, f"{v:g}%", ha="center", fontsize=28, fontweight="bold")
    ax.tick_params(labelsize=22)
    fig.savefig(f"out/graph/{idx:02d}.png", bbox_inches="tight")
    plt.close(fig)

print(f"{len(cues)} graphs -> out/graph/")
