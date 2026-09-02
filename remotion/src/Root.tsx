import { Composition } from "remotion";
import { HoroscopeVideo, horoscopeVideoSchema } from "./HoroscopeVideo";
import React from "react";

// Default props used only for local preview in the Remotion Studio.
// Real renders always pass real props via --props (see render command),
// including the actual audio duration measured by generate_tts.py.
const defaultProps = {
  signName: "Sagittarius",
  captionText:
    "The fire in you is restless today. Trust the instinct that arrives before the doubt does.",
  backgroundVideoPath: "assets/placeholder-bg.mp4",
  audioPath: "assets/placeholder-audio.mp3",
  durationInSeconds: 20,
  bgDurationSeconds: 8,
  dateText: "01 September 2026",
  // Sample timings only, for Studio preview without real props — real
  // renders always get this from generate_tts.py via run_pipeline.py.
  wordTimings: [],
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