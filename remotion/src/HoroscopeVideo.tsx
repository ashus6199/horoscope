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
import { z } from "zod";

export const horoscopeVideoSchema = z.object({
  signName: z.string(),
  captionText: z.string(),
  backgroundVideoPath: z.string(),
  audioPath: z.string(),
  durationInSeconds: z.number(),
});

type Props = z.infer<typeof horoscopeVideoSchema>;

// Splits the caption into short chunks (~6-9 words) so the on-screen text
// reads like paced subtitles rather than one static wall of text.
function chunkCaption(text: string, wordsPerChunk = 7): string[] {
  const words = text.split(/\s+/);
  const chunks: string[] = [];
  for (let i = 0; i < words.length; i += wordsPerChunk) {
    chunks.push(words.slice(i, i + wordsPerChunk).join(" "));
  }
  return chunks;
}

export const HoroscopeVideo: React.FC<Props> = ({
  signName,
  captionText,
  backgroundVideoPath,
  audioPath,
  durationInSeconds,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();

  const chunks = chunkCaption(captionText);
  const framesPerChunk = Math.floor(durationInFrames / chunks.length);
  const activeIndex = Math.min(
    Math.floor(frame / framesPerChunk),
    chunks.length - 1
  );

  // Simple fade in/out per chunk for a less abrupt caption change.
  const localFrame = frame - activeIndex * framesPerChunk;
  const opacity = interpolate(
    localFrame,
    [0, 8, framesPerChunk - 8, framesPerChunk],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Sign name label fades in at the very start, stays subtle throughout.
  const labelOpacity = interpolate(frame, [0, 20], [0, 0.85], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Loop durationInFrames={Math.round(durationInSeconds * fps)}>
        <OffthreadVideo
          src={staticFile(backgroundVideoPath)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
          }}
          muted
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
          }}
        >
          {signName}
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
            opacity,
            fontFamily: "Georgia, serif",
            fontSize: 52,
            lineHeight: 1.3,
            textAlign: "center",
            color: "#ffffff",
            textShadow: "0 2px 12px rgba(0,0,0,0.8)",
          }}
        >
          {chunks[activeIndex]}
        </div>
      </AbsoluteFill>

      <Sequence from={0} durationInFrames={durationInFrames}>
        <Audio src={staticFile(audioPath)} />
      </Sequence>
    </AbsoluteFill>
  );
};
