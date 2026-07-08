"""
台本の [IMG:key] と 話者デフォルト素材が、台帳(assets/irasutoya.json)と
実PNG(remotion/public/irasutoya/<key>.png)に揃っているか検証する。
レンダ前に走らせて「存在しない画像参照」の事故を防ぐ。
使い方: python3 build/check_assets.py scripts/ep01.txt
"""
import sys, re, json, os

MANIFEST = "assets/irasutoya.json"
IMGDIR = "remotion/public/irasutoya"
man = json.load(open(MANIFEST, encoding="utf-8"))
keys = {a["key"]: a for a in man["assets"]}
# 画像は台本の [IMG:] で指定（sticky）。使われているキーだけ検証する。
used = set()
for ln in open(sys.argv[1], encoding="utf-8"):
    m = re.match(r"\s*\[IMG:\s*([\w-]+)\s*\]", ln)
    if m:
        used.add(m.group(1))
if not used:
    print("注意: 台本に [IMG:] が1つもありません（画像なしで進行します）")

problems = []
for k in sorted(used):
    if k not in keys:
        problems.append(f"× 台帳に未登録のキー: [IMG:{k}]  → irasutoya.json に追記を")
    elif not os.path.exists(f"{IMGDIR}/{k}.png"):
        problems.append(f"× PNG未配置: {IMGDIR}/{k}.png（台帳にはあり）")

if problems:
    print("\n".join(problems))
    print(f"\n要対応 {len(problems)} 件。素材を用意してから run.sh を実行してください。")
    sys.exit(1)
print(f"OK: 使用素材 {len(used)} 件すべて台帳・PNGとも存在。")
