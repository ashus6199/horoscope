import { Composition } from "remotion";
import { HoroscopeVideo, horoscopeVideoSchema } from "./HoroscopeVideo";
import React from "react";

// Default props used only for local preview in the Remotion Studio.
// Real renders always pass real props via --props (see render command),
// including actual audio duration and card block timings from run_pipeline.py.
const defaultProps = {
  signName: "Sagittarius",
  captionText:
    "Under a waning Taurus moon, the fire in you meets earth that refuses to hurry. What already has momentum wants your attention now. #sagittarius",
  spokenText:
    "Today's waning Moon in Taurus forms a challenging angle to your Sagittarius sun. This steady earth placement is asking you to ground your restless energy today. Focus on clearing your open tasks and wear forest green. Whatever project you started earlier this week, push to finish it today. And if old disagreements bubble up, don't re-open them. You will vibe best with Aries energy today to amplify your momentum, but handle Gemini with extra care to avoid static.",
  backgroundVideoPath: "assets/placeholder-bg.mp4",
  audioPath: "assets/placeholder-audio.mp3",
  durationInSeconds: 20,
  bgDurationSeconds: 8,
  dateText: "03 September 2026",
  wordTimings: [],
  cardBlocks: [
    {
      key: "hook",
      text: "Taurus Waning Moon tests your Sagittarius fire today.",
      spokenText: "Today's waning Moon in Taurus forms a challenging angle to your Sagittarius sun.",
      start: 0.5,
      end: 4.5,
      isSharpLine: false,
      words: [],
    },
    {
      key: "context",
      text: "Steady earth grounds your pace. Power focus: finish open tasks | Color: forest green.",
      spokenText: "This steady earth placement is asking you to ground your restless energy today. Focus on clearing your open tasks and wear forest green.",
      start: 4.8,
      end: 9.5,
      isSharpLine: false,
      words: [],
    },
    {
      key: "sharp_line",
      text: "Do: Ship Monday's project | Don't: Re-open old arguments.",
      spokenText: "Whatever project you started earlier this week, push to finish it today. And if old disagreements bubble up, don't re-open them.",
      start: 9.8,
      end: 14.5,
      isSharpLine: true,
      words: [],
    },
    {
      key: "compatibility_line",
      text: "Best energy: Aries | Handle with care: Gemini",
      spokenText: "You will vibe best with Aries energy today to amplify your momentum, but handle Gemini with extra care to avoid static.",
      start: 14.8,
      end: 19.5,
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