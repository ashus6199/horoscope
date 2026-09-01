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
      // Duration is derived from the audio length passed in props (not
      // hardcoded) — this is what lets the same composition handle a 16s
      // reading and a 29s reading without any code changes. Story 2.2 AC.
      calculateMetadata={({ props }) => {
        return {
          durationInFrames: Math.round(props.durationInSeconds * FPS),
        };
      }}
    />
  );
};
