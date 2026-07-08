import { Composition, staticFile } from "remotion";
import { Board, Timeline } from "./Board";

// tts.py が out/timeline.json を吐く。run.sh で remotion/public/<ep>/ にコピーする。
const calculateMetadata = async ({ props }: { props: { ep: string } }) => {
  const tl: Timeline = await fetch(
    staticFile(`${props.ep}/timeline.json`)
  ).then((r) => r.json());
  const last = tl.segments[tl.segments.length - 1];
  return {
    durationInFrames: last ? last.start + last.dur : 300,
    fps: tl.fps,
    width: 1920,
    height: 1080,
    props: { ...props, timeline: tl },
  };
};

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Main"
    component={Board as any}
    defaultProps={{ ep: "ep01", timeline: { fps: 30, segments: [] } }}
    calculateMetadata={calculateMetadata as any}
    fps={30}
    width={1920}
    height={1080}
    durationInFrames={300}
  />
);
