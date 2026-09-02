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
  // Per-word timestamps (seconds) from generate_tts.py's edge-tts
  // WordBoundary capture.
  wordTimings: z
    .array(z.object({ word: z.string(), start: z.number(), end: z.number() }))
    .default([]),
});

type Props = z.infer<typeof horoscopeVideoSchema>;
type WordTiming = { word: string; start: number; end: number };
type Chunk = { words: WordTiming[]; start: number; end: number };

// Fallback timings if wordTimings is empty
function buildFallbackTimings(text: string, durationInSeconds: number): WordTiming[] {
  const words = text.split(/\s+/).filter(Boolean);
  const perWord = durationInSeconds / Math.max(words.length, 1);
  return words.map((word, i) => ({
    word,
    start: i * perWord,
    end: i * perWord + perWord * 0.85,
  }));
}

// Groups word timings into short caption cards (~4 words / 2.4s max)
const MAX_WORDS_PER_CHUNK = 4;
const MAX_CHUNK_SECONDS = 2.4;
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

function computeCardFontSize(chunkWords: WordTiming[]): number {
  const totalChars = chunkWords.reduce((sum, w) => sum + w.word.length, 0);
  if (totalChars <= 14) return 132;
  if (totalChars <= 20) return 112;
  if (totalChars <= 26) return 96;
  return 82;
}

const CONTAINER_WIDTH = 860;
const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";
const LINE_HEIGHT = 0.85;

// Individual Word component
// ALWAYS renders in DOM at its exact final layout position.
// If its speech start time hasn't arrived (localFrame < 0), opacity is 0.
// When start time arrives (localFrame >= 0), it pops smoothly into view.
const Word: React.FC<{
  word: string;
  frame: number;
  fps: number;
  delayFrames: number;
  color: string;
  fontSize: number;
}> = ({ word, frame, fps, delayFrames, color, fontSize }) => {
  const localFrame = frame - delayFrames;
  const isVisible = localFrame >= 0;

  const progress = spring({
    frame: Math.max(0, localFrame),
    fps,
    config: { damping: 200, stiffness: 130, mass: 0.6 },
    durationInFrames: 12,
  });

  const opacity = isVisible ? interpolate(progress, [0, 1], [0, 1], { extrapolateLeft: "clamp" }) : 0;
  const translateY = isVisible ? interpolate(progress, [0, 1], [18, 0], { extrapolateLeft: "clamp" }) : 0;
  const scale = isVisible ? interpolate(progress, [0, 1], [1.18, 1], { extrapolateLeft: "clamp" }) : 1;

  return (
    <span
      style={{
        display: "inline-block",
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        marginRight: "0.25em",
        fontSize,
        fontFamily,
        fontWeight: 900,
        letterSpacing: "-0.02em",
        color,
        textShadow: "6px 8px 0px rgba(0,0,0,0.35), 0 16px 30px rgba(0,0,0,0.55)",
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

  // Smooth fade out when the phrase card completes
  const groupOpacity = interpolate(
    localFrame,
    [0, chunkDurationFrames - 6, chunkDurationFrames],
    [1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const fontSize = computeCardFontSize(activeChunk.words);

  // Header label opacity
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

      {/* Bottom gradient so captions stand out cleanly */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 45%, rgba(0,0,0,0.55) 62%, rgba(0,0,0,0.92) 78%, #000 100%)",
        }}
      />

      {/* Top Sign label */}
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

      {/* Caption container — completely fixed layout upfront for all words of the phrase */}
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 370 }}>
        <div style={{ position: "relative", width: CONTAINER_WIDTH }}>
          <div
            style={{
              opacity: groupOpacity,
              lineHeight: LINE_HEIGHT,
              textAlign: "center",
              position: "relative",
            }}
          >
            {activeChunk.words.map((w, i) => (
              <Word
                key={`${activeIndex}-${i}`}
                word={w.word}
                frame={frame}
                fps={fps}
                delayFrames={Math.round(w.start * fps)}
                color={i % 2 === 0 ? WHITE : ORANGE}
                fontSize={fontSize}
              />
            ))}
          </div>
        </div>
      </AbsoluteFill>

      <Sequence from={0} durationInFrames={durationInFrames}>
        <Audio src={staticFile(audioPath)} />
      </Sequence>
    </AbsoluteFill>
  );
};