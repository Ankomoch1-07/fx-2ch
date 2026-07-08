import {
  AbsoluteFill, Audio, Img, Loop, OffthreadVideo, Sequence, staticFile, useCurrentFrame, interpolate, spring,
} from "remotion";
import React from "react";

// 背景動画を実尺ぶんでループ（短い動画でも黒くならない）
const Bg: React.FC<{ src: string; frames?: number }> = ({ src, frames }) => (
  <Loop durationInFrames={Math.max(1, frames ?? 300)}>
    <OffthreadVideo src={staticFile(src)} muted
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover" }} />
  </Loop>
);

export type Seg = {
  i: number; name: string; text: string;
  start: number; dur: number; graph: number | null; img?: string | null;
  phase?: "hook" | "title" | "desc" | "ed" | "main"; telop?: string[];
};
export type Timeline = {
  fps: number; title?: string; opImages?: string[]; edImages?: string[]; se?: string | null;
  bg?: string; opBg?: string; bgFrames?: number; opBgFrames?: number; segments: Seg[];
};

const CHARA: Record<string, { color: string }> = {
  "ずんだもん":   { color: "#c26a00" }, "玄野武宏": { color: "#b3261e" },
  "青山龍星":     { color: "#1b8a3a" }, "九州そら": { color: "#0b63c4" },
  "春日部つむぎ": { color: "#8a1b7a" }, "四国めたん": { color: "#37507a" },
  "No.7":         { color: "#546e7a" },  // 養分ニキ（否定・煽り）
};

const GROUP = 3;
const MOOD_PANIC = ["kaisya_tousan_man", "run_man_suit5", "money_kabu_panic", "business_man_shock", "business_man_cry", "kabu_chart_man_cry"];
const MOOD_UP = ["chance_tsukamu_man", "money_toushi_seikou", "business_man_laugh", "kabu_chart_man_happy", "money_okanemochi", "niyakeru_takuramu_ayashii_man"];
const MOOD_WORRY = ["kinchou_man_walk", "sleep_bad", "pose_ochikomu_businessman", "yopparai_businessman"];
const moodOf = (k: string | null): string =>
  !k ? "calm" : MOOD_PANIC.includes(k) ? "panic" : MOOD_UP.includes(k) ? "up" : MOOD_WORRY.includes(k) ? "worry" : "calm";

export const Board: React.FC<{ ep: string; timeline: Timeline }> = ({ ep, timeline }) => {
  const frame = useCurrentFrame();
  const segs = timeline.segments;
  const idx = Math.max(0, segs.findIndex((s) => frame < s.start + s.dur));
  const cur = segs[idx] ?? segs[segs.length - 1];
  const phase = cur?.phase ?? "main";

  const titleSeg = segs.find((s) => s.phase === "title");
  const descSeg = segs.find((s) => s.phase === "desc");
  const edSeg = segs.find((s) => s.phase === "ed");

  return (
    <AbsoluteFill style={{ fontFamily: "sans-serif" }}>
      <Audio src={staticFile(`${ep}/voice.wav`)} />
      {phase === "hook" && <HookLayer seg={cur} timeline={timeline} />}
      {(phase === "title" || phase === "desc") && titleSeg && (
        <CardLayer timeline={timeline} images={timeline.opImages ?? []} animSeg={titleSeg}
          telopSeg={phase === "desc" ? (descSeg ?? null) : null} titleText={timeline.title ?? ""} playSE={phase === "title"} />
      )}
      {phase === "ed" && edSeg && (
        <CardLayer timeline={timeline} images={timeline.edImages ?? []} animSeg={edSeg}
          telopSeg={edSeg} titleText="ご視聴ありがとうございました！" playSE={false} accent="#1b8a3a" />
      )}
      {phase === "main" && <MainLayer ep={ep} timeline={timeline} segs={segs} idx={idx} cur={cur} />}
    </AbsoluteFill>
  );
};

/* ── フック：別背景＋下部中央テロップ ── */
const HookLayer: React.FC<{ seg: Seg; timeline: Timeline }> = ({ seg, timeline }) => {
  const frame = useCurrentFrame();
  const fps = timeline.fps || 30;
  const pop = spring({ frame: frame - seg.start, fps, config: { damping: 12, mass: 0.6 } });
  return (
    <AbsoluteFill>
      <Bg src={timeline.opBg ?? "bg/clowd.mp4"} frames={timeline.opBgFrames} />
      <AbsoluteFill style={{ background: "rgba(0,0,0,.35)" }} />
      <div style={{
        position: "absolute", left: 0, right: 0, bottom: 150, textAlign: "center",
        transform: `scale(${interpolate(pop, [0, 1], [0.6, 1])})`, opacity: pop,
      }}>
        <span style={{
          display: "inline-block", background: "rgba(18,22,30,.85)", color: "#fff",
          padding: "26px 54px", borderRadius: 18, fontSize: 70, fontWeight: 800, letterSpacing: 2,
          border: "4px solid rgba(255,255,255,.85)",
        }}>{seg.text}</span>
      </div>
    </AbsoluteFill>
  );
};

/* ── カード（OP説明 / ED 共通）：上=タイトル / 中=画像 / 下=チャンクテロップ ── */
const CardLayer: React.FC<{
  timeline: Timeline; images: string[]; animSeg: Seg; telopSeg: Seg | null;
  titleText: string; playSE: boolean; accent?: string;
}> = ({ timeline, images, animSeg, telopSeg, titleText, playSE, accent = "#c62828" }) => {
  const frame = useCurrentFrame();
  const fps = timeline.fps || 30;
  const tt = frame - animSeg.start;
  const titleScale = interpolate(spring({ frame: tt, fps, config: { damping: 9, mass: 0.5 } }), [0, 1], [1.35, 1]);

  let chunk = "";
  if (telopSeg) {
    const chunks = telopSeg.telop ?? [telopSeg.text];
    const prog = interpolate(frame - telopSeg.start, [0, telopSeg.dur], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
    const lens = chunks.map((c) => c.length);
    const total = lens.reduce((a, b) => a + b, 0) || 1;
    let acc = 0, ci = 0;
    for (let k = 0; k < chunks.length; k++) { if (prog < (acc + lens[k] / total)) { ci = k; break; } acc += lens[k] / total; ci = k; }
    chunk = chunks[ci];
  }

  return (
    <AbsoluteFill>
      <Bg src={timeline.opBg ?? "bg/clowd.mp4"} frames={timeline.opBgFrames} />
      <AbsoluteFill style={{ background: "rgba(0,0,0,.45)" }} />
      {playSE && timeline.se && (
        <Sequence from={animSeg.start} durationInFrames={150} layout="none">
          <Audio src={staticFile(timeline.se)} volume={1} />
        </Sequence>
      )}

      <div style={{
        position: "absolute", top: 90, left: 80, right: 80, textAlign: "center",
        transform: `scale(${titleScale})`, opacity: interpolate(tt, [0, 4], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
      }}>
        <span style={{
          display: "inline-block", background: accent, color: "#fff",
          padding: "22px 46px", borderRadius: 14, fontSize: 58, fontWeight: 800, lineHeight: 1.25,
          boxShadow: "0 8px 24px rgba(0,0,0,.45)",
        }}>{titleText}</span>
      </div>

      <div style={{
        position: "absolute", top: 330, left: 0, right: 0, height: 470,
        display: "flex", justifyContent: "center", alignItems: "center", gap: 70,
      }}>
        {images.map((k, n) => {
          const s = spring({ frame: tt - 12 - n * 9, fps, config: { damping: 11, mass: 0.7 } });
          return (
            <Img key={k} src={staticFile(`irasutoya/${k}.png`)}
              style={{
                height: 430, transform: `scale(${interpolate(s, [0, 1], [0.3, 1])}) rotate(${interpolate(s, [0, 1], [-8, 0])}deg)`,
                opacity: s, filter: "drop-shadow(0 10px 18px rgba(0,0,0,.45))",
              }} />
          );
        })}
      </div>

      {telopSeg && (
        <div style={{
          position: "absolute", left: 160, right: 160, bottom: 100,
          background: "rgba(18,22,30,.82)", borderRadius: 16, padding: "26px 44px",
          minHeight: 120, display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <span style={{ color: "#fff", fontSize: 48, fontWeight: 700, lineHeight: 1.4, textAlign: "center" }}>{chunk}</span>
        </div>
      )}
    </AbsoluteFill>
  );
};

/* ── 本編：掲示板レイアウト（3レス送り＋雰囲気アニメ） ── */
const MainLayer: React.FC<{ ep: string; timeline: Timeline; segs: Seg[]; idx: number; cur: Seg }> = ({ ep, timeline, segs, idx, cur }) => {
  const frame = useCurrentFrame();
  const fps = timeline.fps || 30;

  const mainSegs = segs.filter((s) => (s.phase ?? "main") === "main");
  const mIdx = Math.max(0, mainSegs.findIndex((s) => s.i === cur.i));
  const page = Math.floor(mIdx / GROUP);
  const visible = mainSegs.filter((s, k) => Math.floor(k / GROUP) === page && k <= mIdx);

  const imgKey = cur?.img || null;
  let sIdx = idx;
  while (sIdx > 0 && segs[sIdx - 1]?.img === imgKey && (segs[sIdx - 1]?.phase ?? "main") === "main") sIdx--;
  const t = frame - (segs[sIdx]?.start ?? 0);
  const ein = interpolate(t, [0, 10], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  const enterY = interpolate(ein, [0, 1], [70, 0]);
  const enterSc = interpolate(ein, [0, 1], [0.9, 1]);
  const ts = t / fps;
  const mood = moodOf(imgKey);
  let tx = 0, ty = 0, rot = 0;
  if (mood === "panic") { tx = Math.sin(frame * 0.8) * 7; rot = Math.sin(frame * 0.8) * 1.4; }
  else if (mood === "up") { ty = -Math.abs(Math.sin(ts * 3.0)) * 20; }
  else if (mood === "worry") { rot = Math.sin(ts * 1.1) * 2.2; ty = Math.sin(ts * 1.1) * 4; }
  else { ty = Math.sin(ts * 1.4) * 9; }

  const showGraph = cur?.graph != null;

  return (
    <AbsoluteFill>
      <Bg src={timeline.bg ?? "bg/night.mp4"} frames={timeline.bgFrames} />

      {/* グラフ表示中は掲示板要素（タイトル帯・レス・立ち絵）を出さない */}
      {!showGraph && (
        <>
          <div style={{
            position: "absolute", top: 0, right: 0, maxWidth: 1260,
            background: "rgba(18,22,30,.9)", color: "#fff",
            padding: "21px 38px 21px 58px", fontSize: 36, fontWeight: 700,
            clipPath: "polygon(46px 0, 100% 0, 100% 100%, 0 100%)", whiteSpace: "nowrap",
          }}>{timeline.title ?? ""}</div>

          {imgKey && (
            <Img src={staticFile(`irasutoya/${imgKey}.png`)}
              style={{
                position: "absolute", right: 77, bottom: 0, height: 691, transformOrigin: "bottom center",
                transform: `translate(${tx}px, ${enterY + ty}px) scale(${enterSc})`, opacity: ein,
              }} />
          )}

          <div style={{ position: "absolute", left: 58, top: 96, width: 922, display: "flex", flexDirection: "column", gap: 23 }}>
            {visible.map((s) => (
              <div key={s.i} style={{
                background: "#fff", borderRadius: 19, padding: "23px 31px",
                border: `7px solid ${CHARA[s.name]?.color ?? "#333"}`, boxShadow: "0 7px 17px rgba(0,0,0,.28)",
                fontSize: 40, fontWeight: 700, lineHeight: 1.36, color: "#111", alignSelf: "flex-start",
              }}>{s.text}</div>
            ))}
          </div>
        </>
      )}

      {/* 解説グラフ：全画面・不透明で背景の掲示板を完全に隠す */}
      {showGraph && (
        <AbsoluteFill style={{
          background: "#0b120d", alignItems: "center", justifyContent: "center",
          opacity: interpolate(frame - cur.start, [0, 8], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" }),
        }}>
          <Img src={staticFile(`${ep}/graph/${String(cur.graph).padStart(2, "0")}.png`)}
            style={{ width: 1560, borderRadius: 19, background: "#fff", padding: 25 }} />
        </AbsoluteFill>
      )}
    </AbsoluteFill>
  );
};
