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
import { loadFont } from "@remotion/google-fonts/Inter";
import { z } from "zod";

const { fontFamily } = loadFont("normal", { weights: ["800", "900"] });

export const horoscopeVideoSchema = z.object({
  signName: z.string(),
  captionText: z.string(),
  backgroundVideoPath: z.string(),
  audioPath: z.string(),
  durationInSeconds: z.number(),
  bgDurationSeconds: z.number(),
  dateText: z.string(),
  wordTimings: z
    .array(z.object({ word: z.string(), start: z.number(), end: z.number() }))
    .default([]),
});

type Props = z.infer<typeof horoscopeVideoSchema>;
type WordTiming = { word: string; start: number; end: number };
type Chunk = { words: WordTiming[]; start: number; end: number };

function buildFallbackTimings(text: string, durationInSeconds: number): WordTiming[] {
  const words = text.split(/\s+/).filter(Boolean);
  const perWord = durationInSeconds / Math.max(words.length, 1);
  return words.map((word, i) => ({
    word,
    start: i * perWord,
    end: i * perWord + perWord * 0.85,
  }));
}

// Character-based chunking (~22-25 characters max per card block)
// This avoids artificial 3-word cutoffs for tiny words ("as the moon")
// and ensures long words ("earthbound") get their own focused space.
const MAX_CHARS_PER_CHUNK = 24;
const MAX_CHUNK_SECONDS = 2.4;
const PAUSE_GAP_SECONDS = 0.35;

function chunkWordTimings(words: WordTiming[]): Chunk[] {
  if (words.length === 0) return [];
  const chunks: Chunk[] = [];
  let current: WordTiming[] = [words[0]];
  let currentChars = words[0].word.length;

  for (let i = 1; i < words.length; i++) {
    const prev = words[i - 1];
    const word = words[i];
    const gap = word.start - prev.end;
    const chunkDuration = word.end - current[0].start;
    const shouldBreak =
      gap > PAUSE_GAP_SECONDS ||
      currentChars + word.word.length + 1 > MAX_CHARS_PER_CHUNK ||
      chunkDuration > MAX_CHUNK_SECONDS;

    if (shouldBreak) {
      chunks.push({ words: current, start: current[0].start, end: current[current.length - 1].end });
      current = [word];
      currentChars = word.word.length;
    } else {
      current.push(word);
      currentChars += word.word.length + 1;
    }
  }
  chunks.push({ words: current, start: current[0].start, end: current[current.length - 1].end });
  return chunks;
}

// Safely compute font size for a word based on character length
// Enforces that words NEVER exceed the 820px safe width boundary.
function computeWordFontSize(word: string, isEmphasized: boolean): number {
  const baseSize = isEmphasized ? 116 : 94;
  // Inter 900 bold char width factor is ~0.62 * fontSize
  const maxSafeSize = Math.floor(820 / Math.max(1, word.length * 0.62));
  return Math.min(baseSize, Math.max(54, maxSafeSize));
}

const CONTAINER_WIDTH = 900;
const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";

// Balanced center-relative horizontal offsets for graphic staggered feel
const LINE_OFFSETS = [
  { translateX: -40 }, // Line 1: slightly left of center
  { translateX: 40 },  // Line 2: slightly right of center
  { translateX: -20 }, // Line 3: near center
  { translateX: 30 },  // Line 4: slightly right
];

// Word Component: Positioned in its stationary layout spot
// Appears instantly (opacity 1) at exact speech start frame with zero delay or effect.
const Word: React.FC<{
  word: string;
  frame: number;
  fps: number;
  delayFrames: number;
  color: string;
  fontSize: number;
  offsetX: number;
  isFirstLine: boolean;
}> = ({ word, frame, fps, delayFrames, color, fontSize, offsetX, isFirstLine }) => {
  const isVisible = frame >= delayFrames;

  return (
    <div
      style={{
        display: "block",
        textAlign: "center",
        transform: `translateX(${offsetX}px)`,
        marginTop: isFirstLine ? "0px" : "-12px",
        lineHeight: 0.76,
      }}
    >
      <span
        style={{
          display: "inline-block",
          opacity: isVisible ? 1 : 0,
          fontSize,
          fontFamily,
          fontWeight: 900,
          letterSpacing: "-0.03em",
          textTransform: "lowercase",
          color,
          textShadow:
            "5px 7px 0px rgba(0,0,0,0.65), 0 14px 28px rgba(0,0,0,0.85)",
        }}
      >
        {word}
      </span>
    </div>
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
  wordTimings,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const nowSeconds = frame / fps;

  const words = wordTimings.length > 0 ? wordTimings : buildFallbackTimings(captionText, durationInSeconds);
  const chunks = chunkWordTimings(words);

  let activeIndex = chunks.findIndex((c) => nowSeconds >= c.start && nowSeconds < c.end);
  if (activeIndex === -1) {
    activeIndex = chunks.findIndex((c) => nowSeconds < c.start);
    if (activeIndex === -1) activeIndex = chunks.length - 1;
  }
  const activeChunk = chunks[activeIndex];

  const chunkStartFrame = Math.round(activeChunk.start * fps);
  const chunkEndFrame = Math.round(activeChunk.end * fps);
  const chunkDurationFrames = Math.max(chunkEndFrame - chunkStartFrame, 1);
  const localFrame = frame - chunkStartFrame;

  // Smooth fade-out when phrase ends
  const groupOpacity = interpolate(
    localFrame,
    [0, chunkDurationFrames - 6, chunkDurationFrames],
    [1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const labelOpacity = interpolate(frame, [0, 20], [0, 0.85], { extrapolateRight: "clamp" });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Loop durationInFrames={Math.round((bgDurationSeconds / 0.8) * fps)}>
        <OffthreadVideo
          src={staticFile(backgroundVideoPath)}
          playbackRate={0.8}
          volume={0.3}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </Loop>

      {/* Dark bottom gradient for background contrast */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 40%, rgba(0,0,0,0.65) 60%, rgba(0,0,0,0.95) 78%, #000 100%)",
        }}
      />

      {/* Top Header Sign label */}
      <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 230 }}>
        <div
          style={{
            opacity: labelOpacity,
            fontFamily: "Georgia, serif",
            fontSize: 48,
            letterSpacing: 6,
            textTransform: "uppercase",
            color: "#e8d9c0",
            textAlign: "center",
          }}
        >
          <div>{signName}</div>
          <div style={{ fontSize: 24, letterSpacing: 4, marginTop: 12, opacity: 0.7 }}>{dateText}</div>
        </div>
      </AbsoluteFill>

      {/* Caption container block: Center-aligned on screen, bounded to safe 900px width */}
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 360 }}>
        <div
          style={{
            position: "relative",
            width: "100%",
            maxWidth: CONTAINER_WIDTH,
            margin: "0 auto",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
          }}
        >
          {/* Dark radial glow shade behind text for high contrast pop */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "100%",
              height: "140%",
              borderRadius: "50%",
              background:
                "radial-gradient(ellipse at center, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.65) 55%, rgba(0,0,0,0) 82%)",
              filter: "blur(24px)",
              pointerEvents: "none",
            }}
          />

          {/* Center-balanced staggered vertical stack */}
          <div
            style={{
              position: "relative",
              width: "100%",
              opacity: groupOpacity,
              zIndex: 3,
            }}
          >
            {activeChunk.words.map((w, i) => {
              const isEmphasized = i % 2 !== 0;
              const color = isEmphasized ? ORANGE : WHITE;
              const fontSize = computeWordFontSize(w.word, isEmphasized);
              const offset = LINE_OFFSETS[i % LINE_OFFSETS.length];

              return (
                <Word
                  key={`${activeIndex}-${i}`}
                  word={w.word}
                  frame={frame}
                  fps={fps}
                  delayFrames={Math.round(w.start * fps)}
                  color={color}
                  fontSize={fontSize}
                  offsetX={offset.translateX}
                  isFirstLine={i === 0}
                />
              );
            })}
          </div>
        </div>
      </AbsoluteFill>

      <Sequence from={0} durationInFrames={durationInFrames}>
        <Audio src={staticFile(audioPath)} />
      </Sequence>
    </AbsoluteFill>
  );
};