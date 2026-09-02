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
  // WordBoundary capture. Falls back to an empty array so older props
  // files (or Studio preview without real props) don't crash — see
  // buildFallbackTimings below.
  wordTimings: z
    .array(z.object({ word: z.string(), start: z.number(), end: z.number() }))
    .default([]),
});

type Props = z.infer<typeof horoscopeVideoSchema>;
type WordTiming = { word: string; start: number; end: number };
type Chunk = { words: WordTiming[]; start: number; end: number };

// If a render is ever given props with no wordTimings (shouldn't happen in
// production once run_pipeline.py is updated, but keeps Studio preview and
// any hand-edited props.json from crashing), fall back to evenly spacing
// words across the known audio duration — the same behaviour the old
// chunker had.
function buildFallbackTimings(text: string, durationInSeconds: number): WordTiming[] {
  const words = text.split(/\s+/).filter(Boolean);
  const perWord = durationInSeconds / Math.max(words.length, 1);
  return words.map((word, i) => ({
    word,
    start: i * perWord,
    end: i * perWord + perWord * 0.85,
  }));
}

// Groups word timings into short on-screen "cards" the way an editor would
// pace subtitles: break on a natural pause in speech (>0.35s gap) or once a
// card would get too long to read comfortably (>5 words / >2.2s).
const MAX_WORDS_PER_CHUNK = 5;
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

// Picks one word per chunk to visually emphasize, the way an editor would
// highlight the word that actually carries the meaning. Simple heuristic:
// the longest word, skipping tiny connective words so it doesn't land on
// "the"/"and"/etc.
const STOP_WORDS = new Set([
  "the", "and", "you", "your", "have", "been", "that", "this",
  "with", "will", "for", "are", "not", "but", "was", "into",
]);

function pickEmphasisWordIndex(words: WordTiming[]): number {
  let bestIdx = 0;
  let bestLen = 0;
  words.forEach((w, i) => {
    const clean = w.word.replace(/[^a-zA-Z]/g, "").toLowerCase();
    if (STOP_WORDS.has(clean)) return;
    if (clean.length > bestLen) {
      bestLen = clean.length;
      bestIdx = i;
    }
  });
  return bestIdx;
}

// One "hero" chunk per video gets the hand-drawn oval around it — the
// chunk whose emphasized word is the longest across the whole caption.
// Mirrors the reference clip, where the oval calls out a single key
// phrase rather than appearing on every card.
function pickHeroChunkIndex(chunks: Chunk[]): number {
  let bestChunkIdx = 0;
  let bestLen = 0;
  chunks.forEach((chunk, i) => {
    const emphasisIdx = pickEmphasisWordIndex(chunk.words);
    const clean = chunk.words[emphasisIdx].word.replace(/[^a-zA-Z]/g, "");
    if (clean.length > bestLen) {
      bestLen = clean.length;
      bestChunkIdx = i;
    }
  });
  return bestChunkIdx;
}

const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";

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
    durationInFrames: 14,
  });

  const entranceOpacity = interpolate(progress, [0, 1], [0, 1], {
    extrapolateLeft: "clamp",
  });
  const translateY = interpolate(progress, [0, 1], [14, 0], {
    extrapolateLeft: "clamp",
  });
  const scale = interpolate(progress, [0, 1], [0.9, 1], {
    extrapolateLeft: "clamp",
  });

  return (
    <span
      style={{
        display: "inline-block",
        opacity: entranceOpacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        marginRight: 16,
        fontFamily,
        fontWeight: 900,
        letterSpacing: "-0.02em",
        textTransform: "lowercase",
        color: emphasized ? ORANGE : WHITE,
        textShadow: emphasized
          ? "0 10px 26px rgba(0,0,0,0.6), 0 0 22px rgba(255,114,0,0.35)"
          : "0 10px 26px rgba(0,0,0,0.6)",
      }}
    >
      {word}
    </span>
  );
};

// Two overlapping, slightly offset/rotated ellipse strokes, drawn in with
// a stroke-dashoffset animation — reproduces the "hand sketched" double
// line look from the reference clip instead of a single perfect ellipse.
const HandDrawnOval: React.FC<{ drawProgress: number }> = ({ drawProgress }) => {
  const dashOffset = interpolate(drawProgress, [0, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const ovalPath = "M40,110 C40,40 660,30 660,110 C660,190 40,190 40,110 Z";

  return (
    <svg
      viewBox="0 0 700 220"
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
        width: "115%",
        transform: "translate(-50%, -50%)",
        overflow: "visible",
        pointerEvents: "none",
      }}
    >
      <path
        d={ovalPath}
        fill="none"
        stroke={WHITE}
        strokeWidth={6}
        strokeLinecap="round"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={dashOffset}
      />
      <path
        d={ovalPath}
        fill="none"
        stroke={WHITE}
        strokeWidth={4}
        strokeLinecap="round"
        opacity={0.55}
        transform="translate(6,-5) rotate(1.5 350 110)"
        pathLength={1}
        strokeDasharray={1}
        strokeDashoffset={dashOffset}
      />
    </svg>
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
  const heroChunkIndex = chunks.length > 0 ? pickHeroChunkIndex(chunks) : -1;

  // Find the chunk whose [start, end) window contains the current playback
  // time — this is what makes captions land exactly when each word is
  // actually spoken, instead of an even time-slice of the total duration.
  let activeIndex = chunks.findIndex((c) => nowSeconds >= c.start && nowSeconds < c.end);
  if (activeIndex === -1) {
    // Between chunks (a pause) or past the last one — hold the nearest chunk.
    activeIndex = chunks.findIndex((c) => nowSeconds < c.start);
    if (activeIndex === -1) activeIndex = chunks.length - 1;
  }
  const activeChunk = chunks[activeIndex];

  const chunkStartFrame = Math.round(activeChunk.start * fps);
  const chunkEndFrame = Math.round(activeChunk.end * fps);
  const chunkDurationFrames = Math.max(chunkEndFrame - chunkStartFrame, 1);
  const localFrame = frame - chunkStartFrame;

  // Group-level fade brackets each phrase (smooth in/out at the
  // boundaries); per-word entrance (in Word) animates underneath it, timed
  // to that specific word's real speech onset.
  const groupOpacity = interpolate(
    localFrame,
    [0, 5, chunkDurationFrames - 8, chunkDurationFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const emphasisIdx = pickEmphasisWordIndex(activeChunk.words);

  const ovalProgress = spring({
    frame: localFrame,
    fps,
    config: { damping: 200, stiffness: 90, mass: 0.7 },
    durationInFrames: chunkDurationFrames,
  });

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
          muted
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
        />
      </Loop>

      {/* Bottom-anchored gradient: fully transparent through the upper ~45%
          (creature stays unobscured) and ramps to solid black by ~78% so
          captions sit on a clean plate, not on top of the video. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 45%, rgba(0,0,0,0.55) 62%, rgba(0,0,0,0.92) 78%, #000 100%)",
        }}
      />

      {/* Sign name label — kept clear of the top ~220px Instagram Reels
          safe zone (profile chip / follow button). */}
      <AbsoluteFill
        style={{
          justifyContent: "flex-start",
          alignItems: "center",
          paddingTop: 230,
        }}
      >
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
          <div
            style={{
              fontSize: 24,
              letterSpacing: 4,
              marginTop: 12,
              opacity: 0.7,
            }}
          >
            {dateText}
          </div>
        </div>
      </AbsoluteFill>

      {/* Caption block — anchored inside the IG-safe vertical band
          (roughly y=780 to y=1550 on a 1080x1920 canvas) and capped to an
          860px max width so it never reaches the right-edge icon column
          (like/comment/share/save), which eats ~150px on the right from
          about mid-frame down to the bottom. */}
      <AbsoluteFill
        style={{
          justifyContent: "flex-end",
          alignItems: "center",
          paddingBottom: 370,
        }}
      >
        <div
          style={{
            position: "relative",
            maxWidth: 860,
            paddingLeft: 40,
            paddingRight: 40,
          }}
        >
          {activeIndex === heroChunkIndex && <HandDrawnOval drawProgress={ovalProgress} />}
          <div
            style={{
              opacity: groupOpacity,
              fontSize: 64,
              lineHeight: 1,
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
                emphasized={i === emphasisIdx}
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