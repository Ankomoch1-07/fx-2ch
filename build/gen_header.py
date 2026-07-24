"""
YouTubeチャンネルのヘッダー(2560x1440)を生成。サムネと同じ暖色サンバースト＋
黒文字＋太白フチで、日本語をくっきり描画（AI生成の文字崩れを回避）。
文字は全デバイス安全域(中央1546x423)内に収める。
使い方: python3 build/gen_header.py            （既定の3行で out(=branding/header.png)）
        python3 build/gen_header.py --top "…" --hero "…" --sub "…" --bg 背景画像.png
"""
import argparse
import math
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 2560, 1440
SAFE_W = 1546 - 40                       # 安全域(中央1546)幅から左右マージン
SY0, SY1 = (H - 423) // 2, (H + 423) // 2
BLACK, WHITE, RED = (18, 18, 18), (255, 255, 255), (214, 0, 15)
FONTS = [
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Black.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W8.ttc",
    "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
    "/System/Library/Fonts/Hiragino Sans GB.ttc",
    "/Library/Fonts/Arial Unicode.ttf",
]


def font(s):
    for p in FONTS:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, s)
            except Exception:
                pass
    return ImageFont.load_default()


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def sunburst():
    sw, sh = 320, 180
    sm = Image.new("RGB", (sw, sh))
    px = sm.load()
    cx, cy = sw / 2, sh / 2
    md = math.hypot(cx, cy)
    ci, cm, co = (255, 246, 168), (247, 155, 28), (201, 24, 12)
    for y in range(sh):
        for x in range(sw):
            t = math.hypot(x - cx, y - cy) / md
            px[x, y] = lerp(ci, cm, t / 0.55) if t < 0.55 else lerp(cm, co, (t - 0.55) / 0.45)
    img = sm.resize((W, H)).convert("RGBA")
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    n, R, CX, CY = 28, int(math.hypot(W, H)), W // 2, H // 2
    for i in range(n * 2):
        if i % 2 == 0:
            a0, a1 = math.radians(i * 180 / n), math.radians((i + 1) * 180 / n)
            rd.polygon([(CX, CY), (CX + R * math.cos(a0), CY + R * math.sin(a0)),
                        (CX + R * math.cos(a1), CY + R * math.sin(a1))], fill=(255, 236, 130, 70))
    return Image.alpha_composite(img, rays)


def text_tile(text, fnt, stroke, fill=BLACK):
    dd = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    ws = [dd.textlength(c, font=fnt) for c in text]
    asc, desc = fnt.getmetrics()
    pad = stroke + 14
    Wd, Hd = int(sum(ws)) + pad * 2, asc + desc + pad * 2
    t = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    d = ImageDraw.Draw(t)
    x = pad
    for c, w in zip(text, ws):
        d.text((x + 6, pad + 7), c, font=fnt, fill=(0, 0, 0, 150), stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        x += w
    x = pad
    for c, w in zip(text, ws):
        d.text((x, pad), c, font=fnt, fill=fill, stroke_width=stroke, stroke_fill=WHITE)
        x += w
    return t


def fit(text, maxw, base, fill=BLACK):
    s = base
    while s > 40:
        t = text_tile(text, font(s), max(5, s // 11), fill)
        if t.width <= maxw:
            return t
        s -= 6
    return text_tile(text, font(40), 8, fill)


def pcx(base, t, cy):
    base.alpha_composite(t, (int(W / 2 - t.width / 2), int(cy - t.height / 2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", default="2chマネースレ｜FX・ゴールド")
    ap.add_argument("--hero", default="40代からの投資スレはこちら")
    ap.add_argument("--sub", default="毎週 月・水・金 更新")
    ap.add_argument("--bg", default=None, help="背景画像(AI生成等)。指定時はcoverで敷く")
    ap.add_argument("--out", default=os.path.join("branding", "header.png"))
    args = ap.parse_args()

    if args.bg and os.path.exists(args.bg):
        im = Image.open(args.bg).convert("RGB")
        r = max(W / im.width, H / im.height)
        im = im.resize((int(im.width * r), int(im.height * r)))
        x, y = (im.width - W) // 2, (im.height - H) // 2
        base = im.crop((x, y, x + W, y + H)).convert("RGBA")
    else:
        base = sunburst()

    if args.top:
        pcx(base, fit(args.top, SAFE_W, 90, RED), SY0 + 70)
    pcx(base, fit(args.hero, SAFE_W, 200, BLACK), H // 2 + 10)
    if args.sub:
        pcx(base, fit(args.sub, SAFE_W, 78, BLACK), SY1 - 55)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    base.convert("RGB").save(args.out)
    print(f"done: {args.out} ({W}x{H})")


if __name__ == "__main__":
    main()
