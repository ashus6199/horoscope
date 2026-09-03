import { Composition } from "remotion";
import { HoroscopeVideo, horoscopeVideoSchema } from "./HoroscopeVideo";
import React from "react";

// Default props used only for local preview in the Remotion Studio.
// Real renders always pass real props via --props (see render command),
// including actual audio duration and card block timings from run_pipeline.py.
const defaultProps = {
  signName: "Sagittarius",
  captionText:
    "Under a waning Taurus moon, the fire in you meets earth that refuses to hurry. #sagittarius",
  spokenText:
    "Today's Moon sits in Taurus, waning. Earth energy this steady doesn't rush. Finishing something today will feel better than starting it, Sagittarius. Virgo's steadiness might land easier than usual today.",
  backgroundVideoPath: "assets/placeholder-bg.mp4",
  audioPath: "assets/placeholder-audio.mp3",
  durationInSeconds: 20,
  bgDurationSeconds: 8,
  dateText: "03 September 2026",
  wordTimings: [],
  cardBlocks: [
    {
      key: "hook",
      text: "Today's Moon sits in Taurus, waning.",
      start: 0.5,
      end: 3.5,
      isSharpLine: false,
      words: [],
    },
    {
      key: "context",
      text: "Earth energy this steady doesn't rush. It just keeps going.",
      start: 3.8,
      end: 7.5,
      isSharpLine: false,
      words: [],
    },
    {
      key: "sharp_line",
      text: "Finishing something today will feel better than starting it, Sagittarius.",
      start: 7.8,
      end: 12.5,
      isSharpLine: true,
      words: [],
    },
    {
      key: "compatibility_line",
      text: "Virgo's steadiness might land easier than usual today. Scorpio's intensity could feel like static.",
      start: 12.8,
      end: 17.5,
      isSharpLine: false,
      words: [],
    },
  ],
};

const FPS = 30;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="HoroscopeVideo"
      component={HoroscopeVideo}
      fps={FPS}
      width={1080}
      height={1920}
      schema={horoscopeVideoSchema}
      defaultProps={defaultProps}
      // Total duration = spoken audio duration + 3.0s silent outro CTA card
      calculateMetadata={({ props }) => {
        return {
          durationInFrames: Math.round((props.durationInSeconds + 3.0) * FPS),
        };
      }}
    />
  );
};