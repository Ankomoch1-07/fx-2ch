"""
台本(話者タグ付き .txt) を VOICEVOX で音声化し、
  out/voice.wav      … 全結合音声
  out/subs.tsv       … 字幕(話者\tセリフ)
  out/timeline.json  … Remotion同期用タイムライン(フレーム単位, fps=30)
を出力する。
- [GRAPH:...] は直後の発話セグメントに graph 番号として紐づく。
- [IMG:key] は以降の発話にずっと継続（sticky）で紐づく。
- 音声の結合・長さ計算は Python標準の wave のみ（ffmpeg不要）。
使い方: python3 build/tts.py scripts/ep01.txt
"""
import sys, re, json, wave, requests, os, glob

ENG = "http://localhost:50021"
FPS = 30
PAD = 0.35  # 発話間の無音(秒)
spk = json.load(open("build/speakers.json"))
# 話者ごとの読み上げ速度（実測で全員を同じテンポに正規化。数値↑で速い）
SPEED = {
    "四国めたん": 1.01, "ずんだもん": 1.17, "玄野武宏": 0.95,
    "青山龍星": 1.02, "九州そら": 1.53, "春日部つむぎ": 1.05,
    "No.7": 1.00,
}


def _atom_seconds(data, tag):
    """mvhd/mdhd アトム（同じ構造）から再生秒数を返す。無効なら None。"""
    import struct
    i = data.find(tag)
    if i < 0:
        return None
    ver = data[i + 4]
    try:
        if ver == 0:
            ts = struct.unpack(">I", data[i + 16:i + 20])[0]
            dur = struct.unpack(">I", data[i + 20:i + 24])[0]
        else:
            ts = struct.unpack(">I", data[i + 24:i + 28])[0]
            dur = struct.unpack(">Q", data[i + 28:i + 36])[0]
        return (dur / ts) if (ts and dur) else None
    except struct.error:
        return None


def mp4_duration(path):
    """mp4の再生秒数（ffprobe不要）。mvhdが0/無効ならmdhd(トラック)から取得。"""
    try:
        data = open(path, "rb").read()
    except OSError:
        return None
    return _atom_seconds(data, b"mvhd") or _atom_seconds(data, b"mdhd")


def chunk_telop(text, size=22, hardmax=40):
    """説明テロップを文節（。、！？）で区切りつつ約size文字ごとにまとめる。
    長い文節は割らずそのまま1チャンク（=1〜2行）にし、単語の途中では切らない。
    hardmaxを超える異常に長い文節のみ、やむを得ずsizeで機械分割する。"""
    parts = re.split(r"(?<=[。、！？])", text)
    chunks, buf = [], ""
    for p in parts:
        if not p:
            continue
        if len(buf) + len(p) <= size:
            buf += p
            continue
        if buf:
            chunks.append(buf); buf = ""
        if len(p) <= hardmax:
            buf = p
        else:
            for j in range(0, len(p), size):
                chunks.append(p[j:j + size])
    if buf:
        chunks.append(buf)
    return chunks
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
os.makedirs("out/wav", exist_ok=True)
ep = os.path.splitext(os.path.basename(sys.argv[1]))[0]   # 例: ep02

parts, subs, segs = [], [], []
pending_graph = None      # 次の発話に紐づけるグラフ番号
current_img = None        # 直近の [IMG:] を保持（次の[IMG:]まで継続＝sticky）
pending_phase = "main"    # OP_HOOK/OP_CARD で次の発話に付与、その後mainに戻る
op_images = []            # OPIMG: のタイトルカード用画像リスト
ed_images = []            # EDIMG: のED用画像リスト
forced_bg = None          # [BG: file] で本編背景を明示指定（任意）
forced_opbg = None        # [OPBG: file] でOP背景を明示指定（任意）
graph_count = 0
title = ""
i = 0

for ln in lines:
    s = ln.strip()
    if s.startswith("#") and not title:                 # 動画タイトル→スレタイ帯へ
        title = re.sub(r"【.*?】", "", s.lstrip("# ")).strip()
        continue
    if s == "[OP_HOOK]":
        pending_phase = "hook"; continue
    if s == "[OP_TITLE]":
        pending_phase = "title"; continue
    if s == "[OP_DESC]":
        pending_phase = "desc"; continue
    if s == "[ED]":
        pending_phase = "ed"; continue
    mo = re.match(r"\[OPIMG:\s*(.+?)\]", s)
    if mo:
        op_images = [x.strip() for x in mo.group(1).split(",") if x.strip()]
        continue
    me = re.match(r"\[EDIMG:\s*(.+?)\]", s)
    if me:
        ed_images = [x.strip() for x in me.group(1).split(",") if x.strip()]
        continue
    mb = re.match(r"\[BG:\s*(.+?)\]", s)
    if mb:
        forced_bg = mb.group(1).strip(); continue
    mob = re.match(r"\[OPBG:\s*(.+?)\]", s)
    if mob:
        forced_opbg = mob.group(1).strip(); continue
    if s.startswith("[GRAPH"):
        pending_graph = graph_count
        graph_count += 1
        continue
    mi = re.match(r"\[IMG:\s*([\w-]+)\s*\]", s)           # いらすとや素材（以降ずっと継続）
    if mi:
        current_img = mi.group(1)
        continue
    m = re.match(r"【(.+?)】(.+)", ln)
    if not m:
        continue                                   # #タイトル等はスキップ
    name, txt = m.group(1), m.group(2)
    txt = re.sub(r"\[.*?\]", "", txt).strip()      # [要ファクトチェック]等を除去
    if not txt:
        continue
    # w/ｗ（草の"w"）は字幕には残すが読み上げには渡さない
    speak = re.sub(r"[wWｗＷ]+", "", txt).strip() or txt
    sid = spk.get(name, 3)
    q = requests.post(f"{ENG}/audio_query", params={"text": speak, "speaker": sid}).json()
    q["speedScale"] = SPEED.get(name, 1.05)         # 話者ごとに正規化
    wav_bytes = requests.post(f"{ENG}/synthesis", params={"speaker": sid}, json=q).content
    p = f"out/wav/{i:04d}.wav"
    open(p, "wb").write(wav_bytes)
    parts.append(p)
    subs.append(f"{name}\t{txt}")
    seg = {"i": i, "name": name, "text": txt,
           "graph": pending_graph, "img": current_img, "phase": pending_phase}
    if pending_phase in ("desc", "ed"):
        seg["telop"] = chunk_telop(txt)
    segs.append(seg)
    pending_graph = None
    pending_phase = "main"
    i += 1

# wave のみで結合（各発話の後に無音PADを挿入）。同時に各発話の尺を測る。
params = None
durations = []
frames = []
for p in parts:
    w = wave.open(p, "rb")
    if params is None:
        params = w.getparams()
    durations.append(w.getnframes() / w.getframerate() + PAD)
    frames.append(w.readframes(w.getnframes()))
    w.close()

silence = b"\x00" * (int(params.framerate * PAD) * params.sampwidth * params.nchannels)
out = wave.open("out/voice.wav", "wb")
out.setparams(params)
for fr in frames:
    out.writeframes(fr)
    out.writeframes(silence)
out.close()

cur = 0.0
for seg, dur in zip(segs, durations):
    seg["start"] = round(cur * FPS)
    seg["dur"] = max(1, round(dur * FPS))
    cur += dur

se_files = glob.glob("remotion/public/se/*.mp3") + glob.glob("remotion/public/se/*.wav")
se_path = ("se/" + os.path.basename(se_files[0])) if se_files else None

# 背景動画：bg/ 内のmp4をエピソードごとにローテーション（本編とOPで別々）
# 重い動画はレンダが激遅になるので、自動ローテ対象は30MB以下に限定（[BG:]指定なら重くても使える）
MAXBG = 30 * 1024 * 1024
_bg_all = sorted(glob.glob("remotion/public/bg/*.mp4"))
bg_pool = [os.path.basename(p) for p in _bg_all if os.path.getsize(p) <= MAXBG]
_heavy = [os.path.basename(p) for p in _bg_all if os.path.getsize(p) > MAXBG]
_num = re.search(r"\d+", ep)
_idx = int(_num.group()) if _num else abs(hash(ep)) % 997
def pick_bg(offset, forced, fallback):
    if forced:
        return forced if forced.startswith("bg/") else "bg/" + forced
    if not bg_pool:
        return fallback
    return "bg/" + bg_pool[(_idx + offset) % len(bg_pool)]
main_bg = pick_bg(0, forced_bg, "bg/night.mp4")
op_bg = pick_bg(1, forced_opbg, "bg/clowd.mp4")
def bg_frames(bg):
    d = mp4_duration("remotion/public/" + bg)
    # ループ1周のフレーム数（継ぎ目の黒を避けるため実尺から1フレーム詰める）
    return max(1, int(d * FPS) - 1) if d else 240
main_bg_frames = bg_frames(main_bg)
op_bg_frames = bg_frames(op_bg)
print(f"bg: 本編={main_bg}({main_bg_frames}f) / OP={op_bg}({op_bg_frames}f) （ローテ対象{len(bg_pool)}本" +
      (f" ／ 重すぎ除外: {_heavy}" if _heavy else "") + "）")

json.dump({"fps": FPS, "title": title, "opImages": op_images, "edImages": ed_images,
           "se": se_path, "bg": main_bg, "opBg": op_bg,
           "bgFrames": main_bg_frames, "opBgFrames": op_bg_frames, "segments": segs},
          open("out/timeline.json", "w", encoding="utf-8"), ensure_ascii=False)
open("out/subs.tsv", "w", encoding="utf-8").write("\n".join(subs))
print(f"done: out/voice.wav / out/timeline.json ({len(segs)} segs, {graph_count} graphs)")
