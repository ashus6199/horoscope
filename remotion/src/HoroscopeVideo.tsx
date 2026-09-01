import React from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Loop,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  spring,
  Sequence,
} from "remotion";
import { z } from "zod";

export const horoscopeVideoSchema = z.object({
  signName: z.string(),
  captionText: z.string(),
  backgroundVideoPath: z.string(),
  audioPath: z.string(),
  durationInSeconds: z.number(),
  bgDurationSeconds: z.number(),
  dateText: z.string(),
});

type Props = z.infer<typeof horoscopeVideoSchema>;

// Splits the caption into short phrase groups (~6-9 words) so the on-screen
// text reads like paced subtitles rather than one static wall of text.
function chunkCaption(text: string, wordsPerChunk = 7): string[] {
  const words = text.split(/\s+/);
  const chunks: string[] = [];
  for (let i = 0; i < words.length; i += wordsPerChunk) {
    chunks.push(words.slice(i, i + wordsPerChunk).join(" "));
  }
  return chunks;
}

// Picks one word per phrase to visually emphasize, the way an editor would
// bold the word that actually carries the meaning. Simple heuristic: the
// longest word, skipping tiny connective words so it doesn't land on
// "the"/"and"/etc.
const STOP_WORDS = new Set([
  "the", "and", "you", "your", "have", "been", "that", "this",
  "with", "will", "for", "are", "not", "but", "was", "into",
]);

function pickEmphasisWord(words: string[]): number {
  let bestIdx = 0;
  let bestLen = 0;
  words.forEach((w, i) => {
    const clean = w.replace(/[^a-zA-Z]/g, "").toLowerCase();
    if (STOP_WORDS.has(clean)) return;
    if (clean.length > bestLen) {
      bestLen = clean.length;
      bestIdx = i;
    }
  });
  return bestIdx;
}

const STAGGER_FRAMES = 4; // ~130ms between each word's entrance at 30fps

const Word: React.FC<{
  word: string;
  frame: number;
  fps: number;
  delayFrames: number;
  emphasized: boolean;
}> = ({ word, frame, fps, delayFrames, emphasized }) => {
  const localFrame = frame - delayFrames;

  const progress = spring({
    frame: localFrame,
    fps,
    config: { damping: 200, stiffness: 120, mass: 0.6 },
    durationInFrames: 18,
  });

  const entranceOpacity = interpolate(progress, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
  });
  const translateY = interpolate(progress, [0, 1], [16, 0], {
    extrapolateLeft: "clamp",
  });
  const blurPx = interpolate(progress, [0, 1], [10, 0], {
    extrapolateLeft: "clamp",
  });
  // Emphasized word settles very slightly larger, a soft "landing" rather
  // than a bouncy pop — keeps the mysterious/elegant register.
  const scale = emphasized
    ? interpolate(progress, [0, 1], [0.94, 1.06], { extrapolateLeft: "clamp" })
    : 1;

  return (
    <span
      style={{
        display: "inline-block",
        opacity: entranceOpacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        filter: `blur(${blurPx}px)`,
        marginRight: 14,
        color: emphasized ? "#f0d9a8" : "#ffffff",
        fontStyle: emphasized ? "italic" : "normal",
        fontWeight: emphasized ? 600 : 400,
      }}
    >
      {word}
    </span>
  );
};

export const HoroscopeVideo: React.FC<Props> = ({
  signName,
  captionText,
  backgroundVideoPath,
  audioPath,
  durationInSeconds,
  bgDurationSeconds,
  dateText,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const chunks = chunkCaption(captionText);
  const framesPerChunk = Math.floor(durationInFrames / chunks.length);
  const activeIndex = Math.min(
    Math.floor(frame / framesPerChunk),
    chunks.length - 1
  );
  const chunkStartFrame = activeIndex * framesPerChunk;
  const localFrame = frame - chunkStartFrame;

  // Group-level fade still brackets each phrase (smooth in/out at the
  // boundaries); per-word entrance animates underneath it.
  const groupOpacity = interpolate(
    localFrame,
    [0, 6, framesPerChunk - 10, framesPerChunk],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const activeWords = chunks[activeIndex].split(/\s+/);
  const emphasisIdx = pickEmphasisWord(activeWords);

  // Sign name label fades in at the very start, stays subtle throughout.
  const labelOpacity = interpolate(frame, [0, 20], [0, 0.85], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Loop durationInFrames={Math.round((bgDurationSeconds / 0.8) * fps)}>
        <OffthreadVideo
          src={staticFile(backgroundVideoPath)}
          playbackRate={0.8}
          volume={0.3}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      </Loop>

      {/* Subtle dark gradient so caption text stays legible over any clip */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to top, rgba(0,0,0,0.75) 0%, rgba(0,0,0,0.15) 35%, rgba(0,0,0,0.35) 100%)",
        }}
      />

      <AbsoluteFill
        style={{
          justifyContent: "flex-start",
          alignItems: "center",
          paddingTop: 90,
        }}
      >
        <div
          style={{
            opacity: labelOpacity,
            fontFamily: "Georgia, serif",
            fontSize: 34,
            letterSpacing: 6,
            textTransform: "uppercase",
            color: "#e8d9c0",
            textAlign: "center",
          }}
        >
          <div>{signName}</div>
          <div
            style={{
              fontSize: 18,
              letterSpacing: 4,
              marginTop: 12,
              opacity: 0.7,
            }}
          >
            {dateText}
          </div>
        </div>
      </AbsoluteFill>

      <AbsoluteFill
        style={{
          justifyContent: "flex-end",
          alignItems: "center",
          paddingBottom: 220,
          paddingLeft: 70,
          paddingRight: 70,
        }}
      >
        <div
          style={{
            opacity: groupOpacity,
            fontFamily: "Georgia, serif",
            fontSize: 52,
            lineHeight: 1.35,
            textAlign: "center",
            textShadow: "0 2px 12px rgba(0,0,0,0.8)",
          }}
        >
          {activeWords.map((word, i) => (
            <Word
              key={`${activeIndex}-${i}`}
              word={word}
              frame={localFrame}
              fps={fps}
              delayFrames={i * STAGGER_FRAMES}
              emphasized={i === emphasisIdx}
            />
          ))}
        </div>
      </AbsoluteFill>

      <Sequence from={0} durationInFrames={durationInFrames}>
        <Audio src={staticFile(audioPath)} />
      </Sequence>
    </AbsoluteFill>
  );
};
