import React from "react";
import {
  AbsoluteFill,
  Audio,
  Video,
  Loop,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Sequence,
} from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import { z } from "zod";

const { fontFamily } = loadFont("normal", { weights: ["600", "800", "900"] });

const wordTimingSchema = z.object({ word: z.string(), start: z.number(), end: z.number() });

const cardBlockSchema = z.object({
  key: z.string(),
  text: z.string(),
  spokenText: z.string().optional(),
  start: z.number(),
  end: z.number(),
  isSharpLine: z.boolean().default(false),
  words: z.array(wordTimingSchema).default([]),
});

export const horoscopeVideoSchema = z.object({
  signName: z.string(),
  captionText: z.string(),
  spokenText: z.string().optional(),
  backgroundVideoPath: z.string(),
  audioPath: z.string(),
  durationInSeconds: z.number(),
  bgDurationSeconds: z.number(),
  dateText: z.string(),
  wordTimings: z.array(wordTimingSchema).default([]),
  cardBlocks: z.array(cardBlockSchema).default([]),
});

type Props = z.infer<typeof horoscopeVideoSchema>;

const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";
const LIGHT_GOLD = "#E8D9C0";

export const HoroscopeVideo: React.FC<Props> = ({
  signName,
  captionText,
  spokenText,
  backgroundVideoPath,
  audioPath,
  durationInSeconds,
  bgDurationSeconds,
  dateText,
  wordTimings,
  cardBlocks,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const audioEndFrame = Math.round(durationInSeconds * fps);
  const isAudioFinished = frame >= audioEndFrame;

  // Header fade-in
  const labelOpacity = interpolate(frame, [0, 20], [0, 0.85], { extrapolateRight: "clamp" });

  // Fade out card stack when spoken voiceover finishes
  const stackFadeOut = interpolate(
    frame,
    [audioEndFrame - 15, audioEndFrame],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Outro CTA card fade in
  const outroOpacity = interpolate(
    frame,
    [audioEndFrame - 10, audioEndFrame + 10],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Ensure we always have 4 card slots
  const slots = Array.from({ length: 4 }).map((_, idx) => cardBlocks[idx] || null);

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Background Seamless Loop */}
      <Loop durationInFrames={Math.round((bgDurationSeconds / 0.8) * fps)}>
        <Video
          src={staticFile(backgroundVideoPath)}
          playbackRate={0.8}
          volume={0.3}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </Loop>

      {/* Dark bottom gradient for readability */}
      <AbsoluteFill
        style={{
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0) 25%, rgba(0,0,0,0.55) 55%, rgba(0,0,0,0.92) 85%, #000 100%)",
        }}
      />

      {/* Top Header: Sign Name & Date */}
      <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 180 }}>
        <div
          style={{
            opacity: labelOpacity,
            fontFamily: "Georgia, serif",
            fontSize: 48,
            letterSpacing: 6,
            textTransform: "uppercase",
            color: LIGHT_GOLD,
            textAlign: "center",
          }}
        >
          <div>{signName}</div>
          <div style={{ fontSize: 24, letterSpacing: 4, marginTop: 12, opacity: 0.7 }}>{dateText}</div>
        </div>
      </AbsoluteFill>

      {/* Progressive Disclosure Card Stack with Skeleton Loaders */}
      {!isAudioFinished && (
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", paddingTop: 260, paddingBottom: 200, paddingLeft: 60, paddingRight: 60 }}>
          <div
            style={{
              width: "100%",
              maxWidth: 920,
              opacity: stackFadeOut,
              display: "flex",
              flexDirection: "column",
              gap: 20,
            }}
          >
            {slots.map((block, idx) => {
              if (!block) return null;

              const startFrame = Math.round(block.start * fps);
              const isRevealed = frame >= startFrame;

              if (isRevealed) {
                const blockLocalFrame = frame - startFrame;
                // Smooth 8-frame fade & entrance slide
                const opacity = interpolate(blockLocalFrame, [0, 8], [0, 1], { extrapolateRight: "clamp" });
                const translateY = interpolate(blockLocalFrame, [0, 8], [12, 0], { extrapolateRight: "clamp" });

                if (block.isSharpLine) {
                  // Quote Card treatment for sharp_line
                  return (
                    <div
                      key={block.key || idx}
                      style={{
                        opacity,
                        transform: `translateY(${translateY}px)`,
                        background: "rgba(255, 114, 0, 0.16)",
                        backdropFilter: "blur(16px)",
                        borderLeft: `6px solid ${ORANGE}`,
                        borderTop: "1px solid rgba(255, 114, 0, 0.3)",
                        borderRight: "1px solid rgba(255, 114, 0, 0.3)",
                        borderBottom: "1px solid rgba(255, 114, 0, 0.3)",
                        borderRadius: "0 18px 18px 0",
                        padding: "24px 30px",
                        boxShadow: "0 12px 36px rgba(0,0,0,0.6)",
                      }}
                    >
                      <div
                        style={{
                          fontFamily,
                          fontSize: 36,
                          fontWeight: 900,
                          lineHeight: 1.35,
                          color: WHITE,
                          letterSpacing: "-0.01em",
                          textShadow: "0 2px 10px rgba(0,0,0,0.9)",
                        }}
                      >
                        "{block.text}"
                      </div>
                    </div>
                  );
                }

                // Standard Unlocked Progressive Card Block (Hook, Context, Compatibility)
                return (
                  <div
                    key={block.key || idx}
                    style={{
                      opacity,
                      transform: `translateY(${translateY}px)`,
                      background: "rgba(0, 0, 0, 0.74)",
                      backdropFilter: "blur(14px)",
                      border: "1px solid rgba(255, 255, 255, 0.14)",
                      borderRadius: 16,
                      padding: "20px 28px",
                      boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
                    }}
                  >
                    <div
                      style={{
                        fontFamily,
                        fontSize: 32,
                        fontWeight: 600,
                        lineHeight: 1.4,
                        color: block.key === "hook" ? LIGHT_GOLD : WHITE,
                        opacity: block.key === "compatibility_line" ? 0.9 : 1,
                      }}
                    >
                      {block.text}
                    </div>
                  </div>
                );
              }

              // Skeleton Loader Placeholder Card for unrevealed slots
              const pulseOpacity = 0.22 + 0.14 * Math.sin((frame / 10) + idx * 1.5);

              return (
                <div
                  key={`skeleton-${idx}`}
                  style={{
                    opacity: 0.85,
                    background: "rgba(0, 0, 0, 0.42)",
                    backdropFilter: "blur(10px)",
                    border: "1px solid rgba(255, 255, 255, 0.08)",
                    borderRadius: 16,
                    padding: "22px 28px",
                    display: "flex",
                    flexDirection: "column",
                    gap: 12,
                    boxShadow: "0 4px 16px rgba(0,0,0,0.3)",
                  }}
                >
                  <div
                    style={{
                      height: 20,
                      borderRadius: 6,
                      width: idx % 2 === 0 ? "72%" : "64%",
                      background: `rgba(255, 255, 255, ${pulseOpacity})`,
                      boxShadow: "0 0 12px rgba(255, 255, 255, 0.15)",
                    }}
                  />
                  <div
                    style={{
                      height: 14,
                      borderRadius: 4,
                      width: idx % 2 === 0 ? "40%" : "52%",
                      background: `rgba(255, 255, 255, ${pulseOpacity * 0.6})`,
                    }}
                  />
                </div>
              );
            })}
          </div>
        </AbsoluteFill>
      )}

      {/* Outro Call-To-Action Card (Appears after voiceover finishes) */}
      {frame >= audioEndFrame - 15 && (
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center" }}>
          <div
            style={{
              opacity: outroOpacity,
              textAlign: "center",
              width: "100%",
              maxWidth: 860,
              padding: "44px 48px",
              borderRadius: 24,
              background: "rgba(0, 0, 0, 0.88)",
              backdropFilter: "blur(20px)",
              border: "1px solid rgba(255, 255, 255, 0.18)",
              boxShadow: "0 24px 60px rgba(0,0,0,0.9)",
              zIndex: 10,
            }}
          >
            <div
              style={{
                fontFamily,
                fontSize: 44,
                fontWeight: 800,
                color: WHITE,
                lineHeight: 1.35,
                marginBottom: 20,
              }}
            >
              Daily horoscope uploaded on our story.
            </div>
            <div
              style={{
                fontFamily,
                fontSize: 48,
                fontWeight: 900,
                color: ORANGE,
                letterSpacing: "0.02em",
                textTransform: "uppercase",
                textShadow: "0 4px 20px rgba(255,114,0,0.5)",
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