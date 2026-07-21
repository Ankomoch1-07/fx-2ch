"""
サムネ自動生成。reference_money_thumbnail_template ＋ 参照サムネ構図を忠実に再現（文字以外）。
  ① Opus 4.8 が文言(上下見出し・●●伏せ字・吹き出し4つ＋強調語色・NG語マスキング)を生成
  ② 背景は Pillow で暖色サンバーストを確定描画（決まった構図の忠実再現のため既定はGemini不使用）
     ※どうしてもGemini背景にしたい時だけ USE_GEMINI_BG=1（構図は崩れる前提）
  ③ Pillow合成：黒文字＋太白フチの見出し(●●は赤)、楕円吹き出し＋しっぽ(強調語=赤/青)
  厳密QA：中央30%(半径297)に文字/吹き出しが侵入していないかを自動チェック
出力: out/<ep>_thumb.png（1280x720）
使い方: python3 build/gen_thumbnail.py --ep ep20260720
"""
import argparse
import io
import json
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1280, 720
CX, CY = W // 2, H // 2
CLEAR_R = 297                       # 中央の空けるべき半径（円面積が画像の約30%）
BLACK = (18, 18, 18)
WHITE = (255, 255, 255)
RED = (214, 0, 15)                  # 強調・●●
BLUE = (27, 79, 156)               # 用語/固有名詞の強調
EMPH = {"red": RED, "blue": BLUE}

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


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


# ---------- ① 文言（Opus 4.8, 構造化出力） ----------
SCHEMA = {
    "type": "object",
    "properties": {
        "top": {"type": "string"},
        "bottom": {"type": "string"},
        "bubbles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "emph": {"type": "string"},
                    "color": {"type": "string", "enum": ["red", "blue"]},
                },
                "required": ["text", "emph", "color"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["top", "bottom", "bubbles"],
    "additionalProperties": False,
}

THUMB_SYSTEM = """あなたはYouTube「2chお金/投資スレ」系まとめ動画のサムネ文言作家です。
動画タイトル/テーマから、下記テンプレのサムネ文言をJSONで返します。画像や装飾の指定は不要（文言のみ）。

【文言の型】
- top（上段大見出し）: 煽り/前提。疑問形も可。8〜14字。
- bottom（下段大見出し）: 結論/数字。**核心の数字を1つだけ ●● で伏せる**（最重要の引き。●は全角、必ず2つ）。8〜14字。
- bubbles（四隅の吹き出し4つ）: 2ch風のツッコミ/意見バトル。各 **4〜9字**（短く！四隅に収める）。
  各吹き出しは {text, emph, color}:
    emph = text の中の強調する1語（部分文字列、必ず text に含める）。
    color = "red"（損失/危険/煽り: 溶かした/退場/養分 等）or "blue"（専門用語/固有名詞: ロット/新NISA/オルカン 等）。
- 命令・断定(絶対/必ず/一択)、極端評価(最強/神/優秀ライン)、年齢×金額、固有名詞も効かせる。

【NG語の伏せ字（YouTube規約対策・必須）】暴力/センシティブ語はそのまま使わない。
- 死ぬ→退場/飛ぶ/溶ける/●ぬ、 殺す→潰す/●す。 金融言い換え: 退場/溶かす/焼かれる/養分/含み損/強制ロスカット。
"""


def gen_copy(title, topics):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model="claude-opus-4-8",
        max_tokens=1500,
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        system=THUMB_SYSTEM,
        messages=[{"role": "user", "content":
                   f"動画タイトル:\n{title}\n\n参考テーマ:\n{topics}\n\n"
                   "top / bottom / bubbles(4つ, 各text・emph・color) をJSONで。"}],
    )
    data = json.loads(next(b.text for b in msg.content if b.type == "text"))
    b = (data.get("bubbles") or [])[:4]
    while len(b) < 4:
        b.append({"text": "", "emph": "", "color": "red"})
    data["bubbles"] = b
    return data


# ---------- ② 背景：暖色サンバースト（Pillow確定描画） ----------
def sunburst_bg():
    # 放射グラデ（中央=淡黄 → 中間=橙 → 外周=赤）を小サイズで作って拡大
    sw, sh = 320, 180
    small = Image.new("RGB", (sw, sh))
    px = small.load()
    cx, cy = sw / 2, sh / 2
    maxd = math.hypot(cx, cy)
    c_in, c_mid, c_out = (255, 246, 168), (247, 155, 28), (201, 24, 12)
    for yy in range(sh):
        for xx in range(sw):
            t = math.hypot(xx - cx, yy - cy) / maxd
            col = lerp(c_in, c_mid, t / 0.55) if t < 0.55 else lerp(c_mid, c_out, (t - 0.55) / 0.45)
            px[xx, yy] = col
    img = small.resize((W, H)).convert("RGBA")
    # 放射レイ（交互の明るい黄ウェッジを半透明で重ねる＝サンバースト）
    rays = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    rd = ImageDraw.Draw(rays)
    n = 24
    R = int(math.hypot(W, H))
    for i in range(n * 2):
        if i % 2 == 0:
            a0 = math.radians(i * 180.0 / n)
            a1 = math.radians((i + 1) * 180.0 / n)
            rd.polygon([(CX, CY),
                        (CX + R * math.cos(a0), CY + R * math.sin(a0)),
                        (CX + R * math.cos(a1), CY + R * math.sin(a1))],
                       fill=(255, 236, 130, 70))
    return Image.alpha_composite(img, rays)


def gemini_bg(prompt):
    if not os.environ.get("USE_GEMINI_BG") or not os.environ.get("GEMINI_API_KEY"):
        return None
    try:
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        model = os.environ.get("GEMINI_IMAGE_MODEL", "imagen-4.0-generate-001")
        resp = client.models.generate_images(
            model=model, prompt=prompt,
            config=types.GenerateImagesConfig(number_of_images=1, aspect_ratio="16:9"))
        data = getattr(resp.generated_images[0].image, "image_bytes", None)
        if data:
            print(f"  Gemini背景を生成（model={model}）")
            im = Image.open(io.BytesIO(data)).convert("RGB")
            r = max(W / im.width, H / im.height)
            im = im.resize((int(im.width * r), int(im.height * r)))
            x, y = (im.width - W) // 2, (im.height - H) // 2
            return im.crop((x, y, x + W, y + H)).convert("RGBA")
    except Exception as e:
        print(f"  ! Gemini背景失敗→サンバースト: {e}")
    return None


# ---------- ③ 見出し（黒＋太白フチ＋影、●は赤）＆ 楕円吹き出し ----------
def headline_tile(text, fnt, stroke):
    dd = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    widths = [dd.textlength(c, font=fnt) for c in text]
    asc, desc = fnt.getmetrics()
    pad = stroke + 12
    Wd = int(sum(widths)) + pad * 2
    Hd = asc + desc + pad * 2
    tile = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    x = pad
    for c, w in zip(text, widths):                       # 影
        d.text((x + 5, pad + 6), c, font=fnt, fill=(0, 0, 0, 150),
               stroke_width=stroke, stroke_fill=(0, 0, 0, 150))
        x += w
    x = pad
    for c, w in zip(text, widths):                       # 白フチ＋本体（●は赤）
        col = RED if c in "●" else BLACK
        d.text((x, pad), c, font=fnt, fill=col, stroke_width=stroke, stroke_fill=WHITE)
        x += w
    return tile


def fit_headline(text, maxw, base=124):
    size = base
    while size > 54:
        f = font(size)
        tile = headline_tile(text, f, max(6, size // 11))
        if tile.width <= maxw:
            return tile
        size -= 6
    return headline_tile(text, font(54), 8)


def _make_bubble(text, emph, color, fnt):
    d0 = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    tw = d0.textlength(text, font=fnt)
    asc, desc = fnt.getmetrics()
    th = asc + desc
    padx, pady = 30, 18
    bw, bh = int(tw) + padx * 2, th + pady * 2
    tail = 20
    tile = Image.new("RGBA", (bw, bh + tail), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    # しっぽ（先に描く）→ 楕円を上に重ねてしっぽの上辺を隠す＝下に出っ張るだけ
    d.polygon([(bw // 2 - 15, bh - 8), (bw // 2 + 15, bh - 8), (bw // 2 - 2, bh + tail)],
              fill=WHITE, outline=(0, 0, 0), width=5)
    d.ellipse([0, 0, bw - 1, bh - 1], fill=WHITE, outline=(0, 0, 0), width=6)
    # テキスト（強調語のみ色替え）
    runs = [(text, BLACK)]
    if emph and emph in text:
        i = text.index(emph)
        runs = [(text[:i], BLACK), (emph, EMPH.get(color, RED)), (text[i + len(emph):], BLACK)]
        runs = [r for r in runs if r[0]]
    total = sum(d.textlength(r, font=fnt) for r, _ in runs)
    x = (bw - total) / 2
    ty = (bh - th) / 2
    for r, col in runs:
        d.text((x, ty), r, font=fnt, fill=col)
        x += d.textlength(r, font=fnt)
    return tile


def bubble_tile(text, emph, color, max_w):
    """横幅 max_w に収まるようフォントを自動縮小（中央カラムへはみ出させない）。"""
    if not text:
        return None
    size = 42
    while size >= 26:
        tile = _make_bubble(text, emph, color, font(size))
        if tile.width <= max_w:
            return tile
        size -= 2
    return _make_bubble(text, emph, color, font(26))


def paste_cx(layer, tile, cx, y):
    if tile:
        layer.alpha_composite(tile, (int(cx - tile.width / 2), int(y)))


def paste_center(layer, tile, cx, cy):
    if tile:
        layer.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))


# 中央キャラ用の空きゾーン＝上下見出しの間の中央カラム（x方向）。吹き出しはこの外(左右列)に置く。
CLEAR_X0, CLEAR_X1 = 320, 960          # 中央カラム幅640px。上下は見出しの高さから動的に決定→面積≈30%
SIDE_CX_L, SIDE_CX_R = 158, W - 158    # 左右列の吹き出し中心
BUB_MAXW = 288                          # 吹き出し最大幅（中央カラムへはみ出さない上限）


def qa_box_clear(overlay, box):
    """中央カラム(box)内に文字/吹き出しの不透明画素が無いか。max alphaを返す(0が理想)。"""
    return overlay.crop(box).getchannel("A").getextrema()[1]


def build(data, out_path, bg_prompt=""):
    bg = gemini_bg(bg_prompt) or sunburst_bg()
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    # 上下の大見出し（全幅）
    top_tile = fit_headline(data["top"], W - 40)
    bot_tile = fit_headline(data["bottom"], W - 40)
    paste_cx(overlay, top_tile, W / 2, 8)
    paste_cx(overlay, bot_tile, W / 2, H - bot_tile.height - 6)
    # 中央カラム＝見出しの間
    y0 = top_tile.height + 16
    y1 = H - bot_tile.height - 16
    cys = [y0 + 74, y0 + 74, y1 - 74, y1 - 74]
    cxs = [SIDE_CX_L, SIDE_CX_R, SIDE_CX_L, SIDE_CX_R]
    for cx, cy, bub in zip(cxs, cys, data["bubbles"]):
        paste_center(overlay, bubble_tile(bub.get("text", ""), bub.get("emph", ""),
                                          bub.get("color", "red"), BUB_MAXW), cx, cy)
    # 厳密QA：中央カラム(x:CLEAR_X0..X1, y:見出しの間)が空いているか
    box = (CLEAR_X0, y0, CLEAR_X1, y1)
    maxa = qa_box_clear(overlay, box)
    area_pct = (CLEAR_X1 - CLEAR_X0) * (y1 - y0) / (W * H) * 100
    print(f"  QA中央空き: {'OK' if maxa <= 8 else f'NG(侵入 alpha={maxa})'} "
          f"／ 中央カラム {CLEAR_X1 - CLEAR_X0}x{y1 - y0}px(画像の{area_pct:.0f}%)が空き")
    final = Image.alpha_composite(bg, overlay).convert("RGB")
    final.save(out_path)
    return maxa


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
    print("サムネ文言:", json.dumps(data, ensure_ascii=False))
    out_path = args.out or os.path.join(ROOT, "out", f"{args.ep}_thumb.png")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    build(data, out_path)
    print(f"done: {out_path}")


if __name__ == "__main__":
    main()
