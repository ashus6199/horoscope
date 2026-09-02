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
// words across the known audio duration.
function buildFallbackTimings(text: string, durationInSeconds: number): WordTiming[] {
  const words = text.split(/\s+/).filter(Boolean);
  const perWord = durationInSeconds / Math.max(words.length, 1);
  return words.map((word, i) => ({
    word,
    start: i * perWord,
    end: i * perWord + perWord * 0.85,
  }));
}

// Groups word timings into short caption "cards" — break on a natural
// pause in speech (>0.35s gap) or once a card would get too crowded
// (>4 words / >2.4s), matching the ~4-word phrases in the reference clip.
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

// A single font-size per card (not per-word — in the reference every word
// in a card is the same size). Longer/more-charactered cards scale down a
// step so they still fit the safe-zone width instead of overflowing.
function computeCardFontSize(chunkWords: WordTiming[]): number {
  const totalChars = chunkWords.reduce((sum, w) => sum + w.word.length, 0);
  if (totalChars <= 14) return 132;
  if (totalChars <= 20) return 112;
  if (totalChars <= 26) return 96;
  return 82;
}

// Rough estimate of how many wrapped lines a card will take, used only to
// size the hand-drawn oval around it. This is a heuristic (true wrapping
// depends on exact font metrics the layout engine resolves at render
// time) — close enough for a hand-sketched decorative oval, not meant to
// be pixel-exact. Tune CONTAINER_WIDTH/char-width-factor if the oval
// looks consistently too tight or too loose once rendered.
const CONTAINER_WIDTH = 860;
function estimateCardLines(chunkWords: WordTiming[], fontSize: number): number {
  const avgCharWidth = fontSize * 0.6;
  const charsPerLine = Math.max(1, Math.floor(CONTAINER_WIDTH / avgCharWidth));
  let lines = 1;
  let currentLineLen = 0;
  chunkWords.forEach((w) => {
    const wordLen = w.word.length + 1; // + space
    if (currentLineLen + wordLen > charsPerLine && currentLineLen > 0) {
      lines += 1;
      currentLineLen = wordLen;
    } else {
      currentLineLen += wordLen;
    }
  });
  return lines;
}

const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";
const LINE_HEIGHT = 0.74; // < 1 on purpose: this negative-feeling leading is
// what makes wrapped lines overlap, matching the reference clip's stacked
// look, instead of the usual clear line gaps.

const Word: React.FC<{
  word: string;
  frame: number;
  fps: number;
  delayFrames: number;
  color: string;
  fontSize: number;
}> = ({ word, frame, fps, delayFrames, color, fontSize }) => {
  const localFrame = frame - delayFrames;

  const progress = spring({
    frame: localFrame,
    fps,
    config: { damping: 200, stiffness: 130, mass: 0.6 },
    durationInFrames: 12,
  });

  const opacity = interpolate(progress, [0, 1], [0, 1], { extrapolateLeft: "clamp" });
  const translateY = interpolate(progress, [0, 1], [18, 0], { extrapolateLeft: "clamp" });
  const scale = interpolate(progress, [0, 1], [1.18, 1], { extrapolateLeft: "clamp" });

  return (
    <span
      style={{
        display: "inline-block",
        opacity,
        transform: `translateY(${translateY}px) scale(${scale})`,
        marginRight: "0.22em",
        fontSize,
        fontFamily,
        fontWeight: 900,
        letterSpacing: "-0.02em",
        color,
        // Hard offset shadow (sticker/pop look) layered with a soft
        // ambient shadow underneath, matching the reference's punchy
        // drop shadow rather than a purely blurred glow.
        textShadow:
          "6px 8px 0px rgba(0,0,0,0.35), 0 16px 30px rgba(0,0,0,0.55)",
      }}
    >
      {word}
    </span>
  );
};

// Two overlapping, slightly offset/rotated ellipse strokes — the "hand
// sketched" double-line look — sized to roughly encompass one caption
// card's full stack. Drawn in once at the start of the card and held
// static (not redrawn) for the card's whole duration, then cleared when
// the next card starts and draws its own oval.
const HandDrawnOval: React.FC<{ drawProgress: number; width: number; height: number }> = ({
  drawProgress,
  width,
  height,
}) => {
  const dashOffset = interpolate(drawProgress, [0, 1], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const w = 700;
  const h = 220;
  const ovalPath = `M40,${h / 2} C40,${h * 0.18} ${w - 40},${h * 0.14} ${w - 40},${h / 2} C${w - 40},${h * 0.86} 40,${h * 0.86} 40,${h / 2} Z`;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width={width}
      height={height}
      style={{
        position: "absolute",
        top: "50%",
        left: "50%",
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
        transform={`translate(6,-5) rotate(1.5 ${w / 2} ${h / 2})`}
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

  // Find the card whose [start, end) window contains the current
  // playback time — this is what makes captions land exactly when each
  // word is actually spoken, instead of an even time-slice of the total
  // duration.
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

  // Only fade the whole card out at the very end of its window — entrance
  // is already handled per-word by each Word's own spring, so there's no
  // separate group fade-in (that would fight the word-level pop-in).
  const groupOpacity = interpolate(
    localFrame,
    [0, chunkDurationFrames - 8, chunkDurationFrames],
    [1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  const fontSize = computeCardFontSize(activeChunk.words);

  // Oval size: fixed for the whole video, not recomputed per card. Sized
  // to the tallest card across the entire caption so every card's text
  // fits inside it without the oval ever needing to resize. Drawn in once
  // at frame 0 (see ovalProgress below) and held fully drawn afterward —
  // it does not fade or redraw when cards change underneath it.
  const ovalWidth = CONTAINER_WIDTH + 140;
  const ovalHeight = Math.max(
    ...chunks.map((c) => {
      const fs = computeCardFontSize(c.words);
      const lines = estimateCardLines(c.words, fs);
      return fs * 1.05 + (lines - 1) * fs * LINE_HEIGHT * 0.95 + 90;
    })
  );

  // Keyed off the absolute frame (not localFrame within a card) so the
  // draw-in animation plays exactly once, near the start of the video,
  // then stays fully drawn (dashOffset clamps at 0) for the rest of the
  // render regardless of how many caption cards come and go.
  const ovalProgress = spring({
    frame,
    fps,
    config: { damping: 200, stiffness: 90, mass: 0.7 },
    durationInFrames: 24,
  });

  // Sign name label fades in at the very start, stays subtle throughout.
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

      {/* Bottom-anchored gradient: fully transparent through the upper
          ~45% (creature stays unobscured) and ramps to solid black by
          ~78% so captions sit on a clean plate, not on top of the video. */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 45%, rgba(0,0,0,0.55) 62%, rgba(0,0,0,0.92) 78%, #000 100%)",
        }}
      />

      {/* Sign name label — kept clear of the top ~220px Instagram Reels
          safe zone (profile chip / follow button). */}
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

      {/* Caption block — anchored inside the IG-safe vertical band
          (roughly y=780 to y=1550 on a 1080x1920 canvas) and capped to an
          860px max width so it never reaches the right-edge icon column
          (like/comment/share/save), which eats ~150px on the right from
          about mid-frame down to the bottom. */}
      <AbsoluteFill style={{ justifyContent: "flex-end", alignItems: "center", paddingBottom: 370 }}>
        <div style={{ position: "relative", width: CONTAINER_WIDTH }}>
          <HandDrawnOval drawProgress={ovalProgress} width={ovalWidth} height={ovalHeight} />
          <div
            style={{
              opacity: groupOpacity,
              lineHeight: LINE_HEIGHT,
              textAlign: "center",
              position: "relative",
            }}
          >
            {activeChunk.words
              .filter((w) => nowSeconds >= w.start)
              .map((w, i) => (
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