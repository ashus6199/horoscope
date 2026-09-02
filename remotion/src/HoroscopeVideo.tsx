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

// Group into short cards (3 words max for tight stacked graphic impact)
const MAX_WORDS_PER_CHUNK = 3;
const MAX_CHUNK_SECONDS = 2.2;
const PAUSE_GAP_SECONDS = 0.35;

function chunkWordTimings(words: WordTiming[]): Chunk[] {
  if (words.length === 0) return [];
  const chunks: Chunk[] = [];
  let current: WordTiming[] = [words[0]];

  for (let i = 1; i < words.length; i++) {
    const prev = words[i - 1];
    const word = words[i];
    const gap = word.start - prev.end;
    const chunkDuration = word.end - current[0].start;
    const shouldBreak =
      gap > PAUSE_GAP_SECONDS ||
      current.length >= MAX_WORDS_PER_CHUNK ||
      chunkDuration > MAX_CHUNK_SECONDS;

    if (shouldBreak) {
      chunks.push({ words: current, start: current[0].start, end: current[current.length - 1].end });
      current = [word];
    } else {
      current.push(word);
    }
  }
  chunks.push({ words: current, start: current[0].start, end: current[current.length - 1].end });
  return chunks;
}

const CONTAINER_WIDTH = 860;
const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";



// Word Component: Positioned in its fixed staggered row
const Word: React.FC<{
  word: string;
  frame: number;
  fps: number;
  delayFrames: number;
  color: string;
  fontSize: number;
  alignOffset: { paddingLeft: string; scaleFactor: number; marginTop: string };
}> = ({ word, frame, fps, delayFrames, color, fontSize, alignOffset }) => {
  const localFrame = frame - delayFrames;
  const isVisible = localFrame >= 0;

  const progress = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: { damping: 180, stiffness: 140, mass: 0.6 },
    durationInFrames: 12,
  });

  const opacity = isVisible ? interpolate(progress, [0, 1], [0, 1], { extrapolateLeft: "clamp" }) : 0;
  const translateY = isVisible ? interpolate(progress, [0, 1], [22, 0], { extrapolateLeft: "clamp" }) : 0;
  const scale = isVisible ? interpolate(progress, [0, 1], [1.2, 1], { extrapolateLeft: "clamp" }) : 1;

  const finalFontSize = fontSize * alignOffset.scaleFactor;

  return (
    <div
      style={{
        display: "block",
        paddingLeft: alignOffset.paddingLeft,
        marginTop: alignOffset.marginTop,
        lineHeight: 0.72,
      }}
    >
      <span
        style={{
          display: "inline-block",
          opacity,
          transform: `translateY(${translateY}px) scale(${scale})`,
          fontSize: finalFontSize,
          fontFamily,
          fontWeight: 900,
          letterSpacing: "-0.03em",
          textTransform: "lowercase",
          color,
          textShadow:
            "5px 7px 0px rgba(0,0,0,0.6), 0 14px 28px rgba(0,0,0,0.85)",
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

  // Group fade-out when phrase ends
  const groupOpacity = interpolate(
    localFrame,
    [0, chunkDurationFrames - 6, chunkDurationFrames],
    [1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const labelOpacity = interpolate(frame, [0, 20], [0, 0.85], { extrapolateRight: "clamp" });

  // Staggered layout parameters for 1st, 2nd, 3rd words in a phrase card
  const lineLayouts = [
    { paddingLeft: "8%", scaleFactor: 0.95, marginTop: "0px" },     // Line 1: top left (e.g. "it's")
    { paddingLeft: "30%", scaleFactor: 1.25, marginTop: "-12px" },   // Line 2: middle right, EMPHASIZED big (e.g. "pretty")
    { paddingLeft: "18%", scaleFactor: 1.05, marginTop: "-12px" },   // Line 3: bottom left (e.g. "simple.")
  ];

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

      {/* Dark gradient for background contrast */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 40%, rgba(0,0,0,0.65) 60%, rgba(0,0,0,0.95) 78%, #000 100%)",
        }}
      />

      {/* Header sign label */}
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

      {/* Caption container block */}
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 360 }}>
        <div style={{ position: "relative", width: CONTAINER_WIDTH }}>
          {/* Dark radial glow shade directly behind text for high-contrast pop */}
          <div
            style={{
              position: "absolute",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              width: "110%",
              height: "130%",
              borderRadius: "50%",
              background:
                "radial-gradient(ellipse at center, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.6) 50%, rgba(0,0,0,0) 80%)",
              filter: "blur(20px)",
              pointerEvents: "none",
            }}
          />

          {/* Staggered vertical stack layout */}
          <div
            style={{
              position: "relative",
              opacity: groupOpacity,
              zIndex: 3,
            }}
          >
            {activeChunk.words.map((w, i) => {
              const layout = lineLayouts[i % lineLayouts.length];
              const isEven = i % 2 === 0;
              const color = isEven ? WHITE : ORANGE;
              const baseFontSize = 104;

              return (
                <Word
                  key={`${activeIndex}-${i}`}
                  word={w.word}
                  frame={frame}
                  fps={fps}
                  delayFrames={Math.round(w.start * fps)}
                  color={color}
                  fontSize={baseFontSize}
                  alignOffset={layout}
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