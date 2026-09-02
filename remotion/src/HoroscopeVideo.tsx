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
  const cleaned = text.replace(/[—–-]+/g, " ");
  const words = cleaned.split(/\s+/).filter(Boolean);
  const perWord = durationInSeconds / Math.max(words.length, 1);
  return words.map((word, i) => ({
    word: word.replace(/^[—–-]+|[—–-]+$/g, ""),
    start: i * perWord,
    end: i * perWord + perWord * 0.85,
  }));
}

// Character-based chunking (~22-25 characters max per card block)
// Strictly breaks on sentence-ending punctuation (. ! ?) so a new sentence
// ALWAYS starts fresh on its own card block and never mixes with previous sentences.
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

    // Check if the previous word ended a sentence (. ! ? or ;)
    const isPrevSentenceEnd = /[.!?]$/.test(prev.word.trim());

    const shouldBreak =
      isPrevSentenceEnd ||
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
function computeWordFontSize(word: string, isEmphasized: boolean): number {
  const baseSize = isEmphasized ? 116 : 94;
  const maxSafeSize = Math.floor(820 / Math.max(1, word.length * 0.62));
  return Math.min(baseSize, Math.max(54, maxSafeSize));
}

const CONTAINER_WIDTH = 900;
const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";

// Balanced center-relative horizontal offsets for graphic staggered feel
const LINE_OFFSETS = [
  { translateX: -40 },
  { translateX: 40 },
  { translateX: -20 },
  { translateX: 30 },
];

// Word Component: Positioned in its stationary layout spot
// Appears instantly at exact speech start frame with standard English grammar capitalization.
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
          color,
          textShadow:
            "6px 8px 0px rgba(0,0,0,0.85), 0 16px 32px rgba(0,0,0,0.95)",
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

  const audioEndFrame = Math.round(durationInSeconds * fps);
  const isAudioFinished = frame >= audioEndFrame;

  // Smooth fade-out when phrase ends or audio completes
  const phraseFadeOut = interpolate(
    localFrame,
    [0, chunkDurationFrames - 6, chunkDurationFrames],
    [1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const captionOpacity = isAudioFinished ? 0 : phraseFadeOut;

  // Outro CTA card fade in when spoken reading finishes
  const outroOpacity = interpolate(
    frame,
    [audioEndFrame - 10, audioEndFrame + 10],
    [0, 1],
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

      {/* Dark bottom gradient for background contrast — pushed down so video remains clear */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 60%, rgba(0,0,0,0.45) 75%, rgba(0,0,0,0.85) 90%, #000 100%)",
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

      {/* Caption container block (Active during voiceover reading) */}
      {!isAudioFinished && (
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
                width: "115%",
                height: "145%",
                borderRadius: "50%",
                background:
                  "radial-gradient(ellipse at center, rgba(0,0,0,0.98) 0%, rgba(0,0,0,0.85) 55%, rgba(0,0,0,0) 85%)",
                filter: "blur(18px)",
                pointerEvents: "none",
              }}
            />

            {/* Center-balanced staggered vertical stack */}
            <div
              style={{
                position: "relative",
                width: "100%",
                opacity: captionOpacity,
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
      )}

      {/* Silent Outro Call-To-Action Card (Appears after audio finishes) */}
      {frame >= audioEndFrame - 15 && (
        <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 360 }}>
          <div
            style={{
              opacity: outroOpacity,
              textAlign: "center",
              width: "100%",
              maxWidth: 860,
              padding: "36px 40px",
              borderRadius: 24,
              background: "rgba(0, 0, 0, 0.82)",
              backdropFilter: "blur(16px)",
              border: "1px solid rgba(255, 255, 255, 0.15)",
              boxShadow: "0 20px 50px rgba(0,0,0,0.85)",
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontFamily,
                fontSize: 42,
                fontWeight: 800,
                color: WHITE,
                lineHeight: 1.35,
                marginBottom: 16,
              }}
            >
              Daily horoscope uploaded on our story.
            </div>
            <div
              style={{
                fontFamily,
                fontSize: 46,
                fontWeight: 900,
                color: ORANGE,
                letterSpacing: "0.02em",
                textTransform: "uppercase",
                textShadow: "0 4px 18px rgba(255,114,0,0.45)",
              }}
            >
              Follow for more.
            </div>
          </div>
        </AbsoluteFill>
      )}

      <Sequence from={0} durationInFrames={audioEndFrame}>
        <Audio src={staticFile(audioPath)} />
      </Sequence>
    </AbsoluteFill>
  );
};