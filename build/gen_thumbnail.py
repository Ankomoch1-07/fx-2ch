"""
サムネ自動生成。台本のタイトル/テーマから、reference_money_thumbnail_template の型で
  ① Opus 4.8 が文言(上下見出し・吹き出し4つ・NG語伏せ字)＋Gemini背景プロンプトを生成
  ② 背景ビジュアルを生成：GEMINI_API_KEY があれば Gemini、無ければ Pillow でサンバーストを自前描画
  ③ Pillow で見出し(縦グラデ＋白フチ＋影)・四隅の吹き出しを合成。中央 約430x430 は空ける
     （中央のいらすとや人物は後で手動で載せる運用）
出力: out/<ep>_thumb.png（1280x720）
使い方: python3 build/gen_thumbnail.py --ep ep20260720
"""
import argparse
import json
import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 720
CENTER = (425, 145, 855, 575)                 # 中央の空けるスクエア(約430x430)
RED = (230, 0, 18)                            # #E60012
DARK = (40, 0, 0)                             # 下端の濃い赤〜黒
BLUE = (27, 79, 156)                          # #1B4F9C
STRIPE_A, STRIPE_B = (245, 166, 35), (255, 226, 77)   # オレンジ×黄（テンプレ既定の一例）

FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def font(size):
    for p in FONTS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


# ---------- ① 文言＆背景プロンプト（Opus 4.8, 構造化出力） ----------
SCHEMA = {
    "type": "object",
    "properties": {
        "top": {"type": "string"},          # 上段見出し（煽り/前提）
        "bottom": {"type": "string"},       # 下段見出し（結論/数字, ●●で1つ伏せ）
        "bubbles": {"type": "array", "items": {"type": "string"}},  # 吹き出し4つ
        "bg_prompt": {"type": "string"},    # Gemini背景プロンプト（英語, 文字なし, 中央空け）
    },
    "required": ["top", "bottom", "bubbles", "bg_prompt"],
    "additionalProperties": False,
}

THUMB_SYSTEM = """あなたはYouTube「2chお金/投資スレ」系まとめ動画のサムネ構成作家です。
与えられた動画タイトル/テーマから、下記テンプレに沿ったサムネ文言と背景プロンプトをJSONで返します。

【文言の型】
- top（上段大見出し）: 煽り/前提。疑問形も可。8〜14字目安。
- bottom（下段大見出し）: 結論/数字。**核心の数字を1つだけ ●● で伏せる**（最重要の引き）。8〜14字。
- bubbles（四隅の吹き出し4つ）: 2ch風のツッコミ/意見バトル。各4〜10字（例: 正論やろ / 養分乙 / マジか / ようやっとる？）。
- 命令・断定(絶対/必ず/一択)、極端評価(最強/神/優秀ライン)、年齢×金額、固有名詞(新NISA/オルカン等)を効かせる。

【NG語の伏せ字（YouTube規約対策・必須）】暴力/センシティブ語はそのまま使わない。
- 死ぬ→退場/飛ぶ/溶ける/●ぬ、 殺す→潰す/●す。 金融言い換え: 退場/溶かす/焼かれる/養分/含み損/強制ロスカット。

【bg_prompt（背景・英語）】
- 中央 約1/3(430x430px)を空ける指示を必ず入れる（"leave the central square area empty for a character illustration"）。
- 放射状サンバースト＋2トーンの明るいストライプ、投資/お金/相場を想起させる要素、鮮やかで視認性高め。
- **画像内に文字・数字・ロゴを描かない**（"no text, no letters, no numbers, no watermark"）。16:9。
"""


def gen_copy(title, topics):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=2000,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        system=THUMB_SYSTEM,
        messages=[{"role": "user", "content":
                   f"動画タイトル:\n{title}\n\n参考テーマ:\n{topics}\n\n"
                   "このサムネの top / bottom / bubbles(4つ) / bg_prompt をJSONで。"}],
    )
    data = json.loads(next(b.text for b in msg.content if b.type == "text"))
    b = (data.get("bubbles") or [])[:4]
    while len(b) < 4:
        b.append("")
    data["bubbles"] = b
    return data


# ---------- ② 背景：Gemini（あれば）／Pillowサンバースト（fallback） ----------
def gemini_bg(prompt):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        client = genai.Client(api_key=key)
        model = os.environ.get("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")
        resp = client.models.generate_content(model=model, contents=[prompt])
        for part in resp.candidates[0].content.parts:
            inline = getattr(part, "inline_data", None)
            if inline and getattr(inline, "data", None):
                import io
                img = Image.open(io.BytesIO(inline.data)).convert("RGB")
                return fit_cover(img, W, H)
    except Exception as e:
        print(f"  ! Gemini背景生成に失敗（サンバーストで代替）: {e}")
    return None


def fit_cover(img, w, h):
    r = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * r), int(img.height * r)))
    x = (img.width - w) // 2
    y = (img.height - h) // 2
    return img.crop((x, y, x + w, y + h))


def sunburst_bg():
    """放射サンバースト＋2トーンで背景を自前描画（Geminiなしでも必ず1枚出す）。"""
    img = Image.new("RGB", (W, H), STRIPE_B)
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, H // 2
    R = int(math.hypot(W, H))
    seg = 24
    for i in range(seg * 2):
        a0 = math.radians(i * (360 / (seg * 2)))
        a1 = math.radians((i + 1) * (360 / (seg * 2)))
        if i % 2 == 0:
            d.polygon([(cx, cy),
                       (cx + R * math.cos(a0), cy + R * math.sin(a0)),
                       (cx + R * math.cos(a1), cy + R * math.sin(a1))], fill=STRIPE_A)
    # 上下に横ストライプ帯（見出しの下地）
    d.rectangle([0, 0, W, 150], fill=STRIPE_A)
    d.rectangle([0, H - 170, W, H], fill=STRIPE_A)
    return img


# ---------- ③ Pillow合成：見出し（縦グラデ＋白フチ＋影）・吹き出し ----------
def gradient_line(text, fnt, top_color, bottom_color, stroke=10):
    dd = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bb = dd.textbbox((0, 0), text, font=fnt, stroke_width=stroke)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    pad = 16
    Wd, Hd = tw + pad * 2, th + pad * 2
    ox, oy = pad - bb[0], pad - bb[1]
    fill_mask = Image.new("L", (Wd, Hd), 0)
    ImageDraw.Draw(fill_mask).text((ox, oy), text, font=fnt, fill=255, stroke_width=0)
    out_mask = Image.new("L", (Wd, Hd), 0)
    ImageDraw.Draw(out_mask).text((ox, oy), text, font=fnt, fill=255, stroke_width=stroke, stroke_fill=255)
    tile = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 150), (0, 0), out_mask)
    tile.alpha_composite(shadow, (6, 7))
    white = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    white.paste((255, 255, 255, 255), (0, 0), out_mask)
    tile.alpha_composite(white)
    col = Image.new("RGBA", (1, Hd))
    for y in range(Hd):
        t = y / max(1, Hd - 1)
        col.putpixel((0, y), tuple(int(top_color[k] + (bottom_color[k] - top_color[k]) * t) for k in range(3)) + (255,))
    grad = col.resize((Wd, Hd))
    grad.putalpha(fill_mask)
    tile.alpha_composite(grad)
    return tile


def fit_headline(text, maxw, base=128, stroke=10):
    size = base
    while size > 48:
        f = font(size)
        tile = gradient_line(text, f, RED, DARK, stroke)
        if tile.width <= maxw:
            return tile
        size -= 6
    return gradient_line(text, font(48), RED, DARK, stroke)


def paste_center_x(base, tile, cx, y):
    base.alpha_composite(tile, (int(cx - tile.width / 2), int(y)))


def draw_bubble(base, cx, cy, text, fnt):
    if not text:
        return
    d = ImageDraw.Draw(base)
    bb = d.textbbox((0, 0), text, font=fnt)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    padx, pady = 26, 18
    bw, bh = tw + padx * 2, th + pady * 2
    x0, y0 = int(cx - bw / 2), int(cy - bh / 2)
    d.rounded_rectangle([x0, y0, x0 + bw, y0 + bh], radius=22, fill=(255, 255, 255), outline=(0, 0, 0), width=6)
    d.text((cx - tw / 2 - bb[0], cy - th / 2 - bb[1]), text, font=fnt, fill=(20, 20, 20))


def build(data, out_path):
    bg = gemini_bg(data["bg_prompt"]) or sunburst_bg()
    base = bg.convert("RGBA")
    # 上下の大見出し（縦グラデ＋白フチ＋影）
    paste_center_x(base, fit_headline(data["top"], W - 80), W / 2, 18)
    bottom_tile = fit_headline(data["bottom"], W - 80)
    paste_center_x(base, bottom_tile, W / 2, H - bottom_tile.height - 16)
    # 四隅の吹き出し（中央CENTERには侵入させない）
    bf = font(40)
    pos = [(215, 250), (W - 215, 250), (215, 470), (W - 215, 470)]
    for (cx, cy), txt in zip(pos, data["bubbles"]):
        draw_bubble(base, cx, cy, txt, bf)
    base.convert("RGB").save(out_path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ep", required=True)
    ap.add_argument("--script", default=None)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    script = args.script or os.path.join(ROOT, "scripts", f"{args.ep}.txt")
    title = ""
    for ln in open(script, encoding="utf-8"):
        if ln.strip().startswith("#"):
            title = ln.lstrip("# ").strip()
            break
    topics = read("out/topics.txt") if os.path.exists(os.path.join(ROOT, "out/topics.txt")) else title

    data = gen_copy(title, topics)
    print("サムネ文言:", json.dumps(data, ensure_ascii=False, indent=2))
    out_path = args.out or os.path.join(ROOT, "out", f"{args.ep}_thumb.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    build(data, out_path)
    print(f"done: {out_path}")


if __name__ == "__main__":
    main()
