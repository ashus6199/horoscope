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

const { fontFamily } = loadFont("normal", { weights: ["400", "600", "700", "800", "900"] });

const wordTimingSchema = z.object({ word: z.string(), start: z.number(), end: z.number() });

const cardBlockSchema = z.object({
  key: z.string(),
  text: z.string(),
  spokenText: z.string().optional(),
  start: z.number(),
  end: z.number(),
  isSharpLine: z.boolean().default(false),
  words: z.array(wordTimingSchema).default([]),
  // Structured sub-fields for rich card rendering
  powerFocus: z.string().optional(),
  powerColor: z.string().optional(),
  sharpDo: z.string().optional(),
  sharpDont: z.string().optional(),
  bestSign: z.string().optional(),
  cautionSign: z.string().optional(),
  skyWeatherText: z.string().optional(),
  reflectionQuestion: z.string().optional(),
});

const eventAlertSchema = z.object({
  tier: z.number(),
  type: z.string(),
  label: z.string(),
  badgeAccent: z.string().optional(),
  sign: z.string().optional(),
  planet: z.string().optional(),
  daysRemaining: z.number().optional(),
}).nullable().optional();

export const horoscopeVideoSchema = z.object({
  signName: z.string(),
  captionText: z.string(),
  spokenText: z.string().optional(),
  moonSign: z.string().default(""),
  moonPhase: z.string().default(""),
  moonPhasePct: z.number().default(50.0),
  moonAgeDays: z.number().default(14.0),
  bestSign: z.string().default(""),
  cautionSign: z.string().default(""),
  eventAlert: eventAlertSchema.default(null),
  backgroundVideoPath: z.string(),
  audioPath: z.string(),
  durationInSeconds: z.number(),
  bgDurationSeconds: z.number(),
  dateText: z.string(),
  wordTimings: z.array(wordTimingSchema).default([]),
  cardBlocks: z.array(cardBlockSchema).default([]),
});

type Props = z.infer<typeof horoscopeVideoSchema>;
type CardBlock = z.infer<typeof cardBlockSchema>;
type EventAlert = z.infer<typeof eventAlertSchema>;

// ─── Design Tokens ───────────────────────────────────────────────
const ORANGE = "#FF7200";
const WHITE = "#FFFFFF";
const LIGHT_GOLD = "#E8D9C0";
const EMERALD = "#34D399";
const ROSE = "#FB7185";
const AMBER = "#FBBF24";
const LUNAR_SILVER = "#C4C9D4";

// ─── Zodiac Glyph Map ───────────────────────────────────────────
const ZODIAC_GLYPHS: Record<string, string> = {
  Aries: "♈", Taurus: "♉", Gemini: "♊", Cancer: "♋",
  Leo: "♌", Virgo: "♍", Libra: "♎", Scorpio: "♏",
  Sagittarius: "♐", Capricorn: "♑", Aquarius: "♒", Pisces: "♓",
};

// ─── Moon Phase Icon Map & Resolution ─────────────────────────────
const MOON_ICONS: Record<string, string> = {
  "new moon": "🌑", "waxing crescent": "🌒", "waxing": "🌒",
  "first quarter": "🌓", "waxing gibbous": "🌔",
  "full moon": "🌕",
  "waning gibbous": "🌖", "waning": "🌘",
  "last quarter": "🌗", "waning crescent": "🌘",
};

function getMoonPhaseIcon(phaseLabel?: string, phasePct?: number, ageDays?: number): string {
  if (ageDays !== undefined && ageDays >= 0) {
    const age = ageDays % 29.53;
    if (age < 1.84 || age >= 27.69) return "🌑";
    if (age < 5.53) return "🌒";
    if (age < 9.22) return "🌓";
    if (age < 12.91) return "🌔";
    if (age < 16.61) return "🌕";
    if (age < 20.30) return "🌖";
    if (age < 23.99) return "🌗";
    return "🌘";
  }
  const key = (phaseLabel || "").toLowerCase().trim();
  if (MOON_ICONS[key]) return MOON_ICONS[key];
  if (phasePct !== undefined) {
    if (phasePct < 5) return "🌑";
    if (phasePct > 95) return "🌕";
    return "🌓";
  }
  return "☽";
}

// ─── Shared Card Shell ───────────────────────────────────────────
const CardShell: React.FC<{
  children: React.ReactNode;
  opacity: number;
  translateY: number;
  borderColor?: string;
  bgColor?: string;
}> = ({ children, opacity, translateY, borderColor, bgColor }) => (
  <div
    style={{
      opacity,
      transform: `translateY(${translateY}px)`,
      background: bgColor || "rgba(0, 0, 0, 0.68)",
      backdropFilter: "blur(16px)",
      WebkitBackdropFilter: "blur(16px)",
      border: `1px solid ${borderColor || "rgba(255, 255, 255, 0.12)"}`,
      borderRadius: 18,
      padding: "16px 22px",
      boxShadow: "0 8px 32px rgba(0,0,0,0.45)",
    }}
  >
    {children}
  </div>
);

// ─── Card 1: Hook (Moon Transit) ─────────────────────────────────
const HookCard: React.FC<{
  block: CardBlock;
  moonPhase: string;
  moonPhasePct?: number;
  moonAgeDays?: number;
  eventAlert?: EventAlert;
  opacity: number;
  ty: number;
}> = ({ block, moonPhase, moonPhasePct, moonAgeDays, eventAlert, opacity, ty }) => {
  const moonIcon = getMoonPhaseIcon(moonPhase, moonPhasePct, moonAgeDays);
  const accent = eventAlert?.badgeAccent || "rgba(196, 201, 212, 0.25)";
  return (
    <CardShell opacity={opacity} translateY={ty} borderColor={eventAlert ? `${accent}60` : "rgba(196, 201, 212, 0.25)"}>
      {/* Event Alert Badge (Tier 2 or Tier 3) */}
      {eventAlert && eventAlert.label && (
        <div
          style={{
            fontFamily,
            fontSize: 15,
            fontWeight: 700,
            color: accent,
            textTransform: "uppercase",
            letterSpacing: 3,
            marginBottom: 14,
            paddingBottom: 12,
            borderBottom: `1px solid ${accent}30`,
          }}
        >
          {eventAlert.label}
        </div>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
        {/* Dynamic Glowing Moon Badge */}
        <div
          style={{
            width: 54,
            height: 54,
            borderRadius: "50%",
            background: eventAlert ? `${accent}18` : "rgba(196, 201, 212, 0.12)",
            border: `1.5px solid ${eventAlert ? `${accent}50` : "rgba(196, 201, 212, 0.35)"}`,
            boxShadow: eventAlert ? `0 0 16px ${accent}60` : "0 0 12px rgba(196, 201, 212, 0.2)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 26,
            flexShrink: 0,
          }}
        >
          {moonIcon}
        </div>
        <div style={{ fontFamily, fontSize: 26, fontWeight: 700, color: WHITE, lineHeight: 1.3 }}>
          {block.text}
        </div>
      </div>
    </CardShell>
  );
};

// ─── Card 2: Sky Weather & Retrogrades ───────────────────────────
const SkyWeatherCard: React.FC<{ block: CardBlock; opacity: number; ty: number }> = ({
  block, opacity, ty,
}) => {
  const weatherText = block.skyWeatherText || block.text || "Planetary Transits Active";
  return (
    <CardShell
      opacity={opacity}
      translateY={ty}
      bgColor="rgba(25, 25, 112, 0.28)"
      borderColor="rgba(139, 92, 246, 0.35)"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{
          width: 36, height: 36, borderRadius: "50%",
          background: "rgba(139, 92, 246, 0.2)",
          border: "1.5px solid #8B5CF6",
          boxShadow: "0 0 14px rgba(139, 92, 246, 0.4)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, flexShrink: 0,
        }}>🪐</div>
        <div>
          <div style={{ fontFamily, fontSize: 14, fontWeight: 600, color: "rgba(255,255,255,0.6)", textTransform: "uppercase", letterSpacing: 2, marginBottom: 3 }}>
            Sky Weather
          </div>
          <div style={{ fontFamily, fontSize: 24, fontWeight: 700, color: WHITE, lineHeight: 1.3 }}>
            {weatherText}
          </div>
        </div>
      </div>
    </CardShell>
  );
};

// ─── Card 3: Context (Power Focus + Color) ───────────────────────
const ContextCard: React.FC<{ block: CardBlock; opacity: number; ty: number }> = ({
  block, opacity, ty,
}) => {
  const focus = block.powerFocus || block.text;
  const color = block.powerColor || "";
  const colorHex = color ? colorNameToHex(color) : "#A78BFA";

  return (
    <CardShell
      opacity={opacity}
      translateY={ty}
      borderColor={`${colorHex}45`}
      bgColor="rgba(0, 0, 0, 0.72)"
    >
      <div style={{ display: "flex", gap: 24, alignItems: "stretch" }}>
        {/* Power Focus Column with Power-Color-Tinted Icon Badge */}
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "50%",
                background: `${colorHex}22`,
                border: `1.5px solid ${colorHex}80`,
                boxShadow: `0 0 12px ${colorHex}60`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 16,
                lineHeight: 1,
              }}
            >
              ⚡
            </div>
            <div style={{ fontFamily, fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.6)", textTransform: "uppercase", letterSpacing: 2 }}>
              Power Focus
            </div>
          </div>
          <div style={{ fontFamily, fontSize: 24, fontWeight: 700, color: WHITE, lineHeight: 1.3 }}>
            {focus}
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: 1, background: "rgba(255,255,255,0.12)", alignSelf: "stretch" }} />

        {/* Power Color Column with Dynamic Icon & Glowing Swatch Badge */}
        {color && (
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
              <div
                style={{
                  width: 28,
                  height: 28,
                  borderRadius: "50%",
                  background: `${colorHex}22`,
                  border: `1.5px solid ${colorHex}80`,
                  boxShadow: `0 0 12px ${colorHex}60`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontSize: 16,
                  lineHeight: 1,
                }}
              >
                🎨
              </div>
              <div style={{ fontFamily, fontSize: 16, fontWeight: 600, color: "rgba(255,255,255,0.6)", textTransform: "uppercase", letterSpacing: 2 }}>
                Color
              </div>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              {/* Color Swatch Dot */}
              <div
                style={{
                  width: 22,
                  height: 22,
                  borderRadius: "50%",
                  background: colorHex,
                  border: "2px solid #FFFFFF",
                  boxShadow: `0 0 16px ${colorHex}`,
                  flexShrink: 0,
                }}
              />
              <div style={{ fontFamily, fontSize: 24, fontWeight: 700, color: WHITE, lineHeight: 1.3 }}>
                {color}
              </div>
            </div>
          </div>
        )}
      </div>
    </CardShell>
  );
};

// ─── Card 4: Sharp Line (Do / Don't) ────────────────────────────
const SharpLineCard: React.FC<{ block: CardBlock; opacity: number; ty: number }> = ({
  block, opacity, ty,
}) => {
  const doText = block.sharpDo || block.text;
  const dontText = block.sharpDont || "";
  return (
    <CardShell
      opacity={opacity}
      translateY={ty}
      bgColor="rgba(255, 114, 0, 0.12)"
      borderColor="rgba(255, 114, 0, 0.25)"
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* DO row */}
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{
            width: 32, height: 32, borderRadius: "50%",
            background: "rgba(52, 211, 153, 0.2)",
            border: `2px solid ${EMERALD}`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 18, color: EMERALD, fontWeight: 900, flexShrink: 0,
          }}>✓</div>
          <div style={{ fontFamily, fontSize: 24, fontWeight: 700, color: WHITE, lineHeight: 1.3 }}>
            {doText}
          </div>
        </div>
        {/* Separator */}
        {dontText && <div style={{ height: 1, background: "rgba(255,255,255,0.08)" }} />}
        {/* DON'T row */}
        {dontText && (
          <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
            <div style={{
              width: 32, height: 32, borderRadius: "50%",
              background: "rgba(251, 113, 133, 0.2)",
              border: `2px solid ${ROSE}`,
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 18, color: ROSE, fontWeight: 900, flexShrink: 0,
            }}>✗</div>
            <div style={{ fontFamily, fontSize: 24, fontWeight: 700, color: "rgba(255,255,255,0.85)", lineHeight: 1.3 }}>
              {dontText}
            </div>
          </div>
        )}
      </div>
    </CardShell>
  );
};

// ─── Card 4: Compatibility (Best Energy & Handle With Care) ─────
const CompatibilityCard: React.FC<{
  block: CardBlock; bestSign: string; cautionSign: string;
  opacity: number; ty: number;
}> = ({ block, bestSign, cautionSign, opacity, ty }) => {
  const bestGlyph = ZODIAC_GLYPHS[bestSign] || "★";
  const cautionGlyph = ZODIAC_GLYPHS[cautionSign] || "☆";

  return (
    <CardShell opacity={opacity} translateY={ty}>
      <div style={{ display: "flex", gap: 20, alignItems: "stretch" }}>
        {/* Best Energy Column */}
        {bestSign && (
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
              <div style={{ fontSize: 28, lineHeight: 1, color: EMERALD, filter: `drop-shadow(0 0 8px ${EMERALD}50)` }}>
                {bestGlyph}
              </div>
              <div style={{ fontFamily, fontSize: 22, fontWeight: 800, color: EMERALD, lineHeight: 1.2 }}>
                {bestSign}
              </div>
            </div>
            <div style={{ fontFamily, fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: 2, marginLeft: 38 }}>
              Best Energy
            </div>
          </div>
        )}
        {/* Divider */}
        <div style={{ width: 1, background: "rgba(255,255,255,0.08)", alignSelf: "stretch" }} />
        {/* Caution Column */}
        {cautionSign && (
          <div style={{ flex: 1 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 2 }}>
              <div style={{ fontSize: 28, lineHeight: 1, color: AMBER, filter: `drop-shadow(0 0 8px ${AMBER}50)` }}>
                {cautionGlyph}
              </div>
              <div style={{ fontFamily, fontSize: 22, fontWeight: 800, color: AMBER, lineHeight: 1.2 }}>
                {cautionSign}
              </div>
            </div>
            <div style={{ fontFamily, fontSize: 13, fontWeight: 600, color: "rgba(255,255,255,0.5)", textTransform: "uppercase", letterSpacing: 2, marginLeft: 38 }}>
              Handle With Care
            </div>
          </div>
        )}
      </div>
    </CardShell>
  );
};

// ─── Card 5: Dedicated Journal Reflection ────────────────────────
const ReflectionCard: React.FC<{ block: CardBlock; opacity: number; ty: number }> = ({
  block, opacity, ty,
}) => {
  const question = block.reflectionQuestion || block.text;

  return (
    <CardShell
      opacity={opacity}
      translateY={ty}
      bgColor="rgba(255, 215, 0, 0.10)"
      borderColor="rgba(255, 215, 0, 0.28)"
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div
          style={{
            width: 36,
            height: 36,
            borderRadius: "50%",
            background: "rgba(255, 215, 0, 0.18)",
            border: `1.5px solid ${LIGHT_GOLD}`,
            boxShadow: `0 0 14px rgba(255, 215, 0, 0.4)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 18,
            flexShrink: 0,
          }}
        >
          💬
        </div>
        <div>
          <div
            style={{
              fontFamily,
              fontSize: 12,
              fontWeight: 700,
              color: LIGHT_GOLD,
              textTransform: "uppercase",
              letterSpacing: 2.5,
              marginBottom: 2,
            }}
          >
            Daily Reflection
          </div>
          <div
            style={{
              fontFamily: "Georgia, serif",
              fontSize: 22,
              fontWeight: 700,
              color: WHITE,
              lineHeight: 1.3,
              fontStyle: "italic",
            }}
          >
            "{question}"
          </div>
        </div>
      </div>
    </CardShell>
  );
};

// ─── Color Name → Hex helper ─────────────────────────────────────
function colorNameToHex(name: string): string {
  const map: Record<string, string> = {
    "forest green": "#228B22", "deep navy": "#1B2A4A", "midnight blue": "#191970",
    "crimson": "#DC143C", "ruby": "#9B111E", "scarlet": "#FF2400",
    "burnt orange": "#CC5500", "amber": "#FFBF00", "gold": "#FFD700",
    "emerald": "#50C878", "sage": "#9DC183", "olive": "#808000",
    "lavender": "#E6E6FA", "violet": "#8B5CF6", "plum": "#8E4585",
    "coral": "#FF7F50", "warm coral": "#FF6F59", "peach": "#FFDAB9", "blush": "#DE5D83",
    "silver": "#C0C0C0", "charcoal": "#36454F", "ivory": "#FFFFF0",
    "teal": "#008080", "turquoise": "#40E0D0", "cyan": "#00FFFF", "aquamarine": "#7FFFD4",
    "rose": "#FF007F", "magenta": "#FF00FF", "burgundy": "#800020", "terracotta": "#E2725B",
    "rust": "#B7410E", "copper": "#B87333", "bronze": "#CD7F32",
    "white": "#FFFFFF", "black": "#000000", "red": "#EF4444",
    "blue": "#3B82F6", "green": "#22C55E", "yellow": "#EAB308",
    "orange": "#F97316", "pink": "#EC4899", "purple": "#A855F7",
    "indigo": "#6366F1", "deep indigo": "#4B0082", "electric violet": "#8B5CF6",
    "sky blue": "#87CEEB", "royal blue": "#4169E1",
  };
  const key = name.toLowerCase().trim();
  return map[key] || "#A78BFA"; // fallback to soft violet
}

// ─── Main Component ──────────────────────────────────────────────
export const HoroscopeVideo: React.FC<Props> = ({
  signName, captionText, spokenText,
  moonSign, moonPhase, moonPhasePct, moonAgeDays, bestSign, cautionSign,
  eventAlert,
  backgroundVideoPath, audioPath,
  durationInSeconds, bgDurationSeconds,
  dateText, wordTimings, cardBlocks,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const audioEndFrame = Math.round(durationInSeconds * fps);
  const isAudioFinished = frame >= audioEndFrame;

  // Header fade-in
  const labelOpacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: "clamp" });

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

  // Ensure we have 6 card slots for progressive disclosure
  const slots = Array.from({ length: 6 }).map((_, idx) => cardBlocks[idx] || null);

  // Render the correct card component based on block.key
  const renderCard = (block: CardBlock, opacity: number, ty: number) => {
    switch (block.key) {
      case "hook":
        return (
          <HookCard
            block={block}
            moonPhase={moonPhase}
            moonPhasePct={moonPhasePct}
            moonAgeDays={moonAgeDays}
            eventAlert={eventAlert}
            opacity={opacity}
            ty={ty}
          />
        );
      case "sky_weather":
        return <SkyWeatherCard block={block} opacity={opacity} ty={ty} />;
      case "context":
        return <ContextCard block={block} opacity={opacity} ty={ty} />;
      case "sharp_line":
        return <SharpLineCard block={block} opacity={opacity} ty={ty} />;
      case "compatibility_line":
        return (
          <CompatibilityCard
            block={block}
            bestSign={block.bestSign || bestSign}
            cautionSign={block.cautionSign || cautionSign}
            opacity={opacity}
            ty={ty}
          />
        );
      case "reflection":
        return <ReflectionCard block={block} opacity={opacity} ty={ty} />;
    }
  };

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
      <AbsoluteFill style={{ justifyContent: "flex-start", alignItems: "center", paddingTop: 150 }}>
        <div
          style={{
            opacity: labelOpacity,
            fontFamily: "Georgia, serif",
            fontSize: 46,
            letterSpacing: 6,
            textTransform: "uppercase",
            color: LIGHT_GOLD,
            textAlign: "center",
          }}
        >
          <div>{signName}</div>
          <div style={{ fontSize: 22, letterSpacing: 4, marginTop: 10, opacity: 0.7 }}>{dateText}</div>
        </div>
      </AbsoluteFill>

      {/* Progressive Disclosure Card Stack with Skeleton Loaders */}
      {!isAudioFinished && (
        <AbsoluteFill style={{ justifyContent: "center", alignItems: "center", paddingTop: 230, paddingBottom: 160, paddingLeft: 60, paddingRight: 60 }}>
          <div
            style={{
              width: "100%",
              maxWidth: 920,
              opacity: stackFadeOut,
              display: "flex",
              flexDirection: "column",
              gap: 14,
            }}
          >
            {slots.map((block, idx) => {
              if (!block) return null;

              const startFrame = Math.round(block.start * fps);
              const isRevealed = frame >= startFrame;

              if (isRevealed) {
                const blockLocalFrame = frame - startFrame;
                const opacity = interpolate(blockLocalFrame, [0, 10], [0, 1], { extrapolateRight: "clamp" });
                const translateY = interpolate(blockLocalFrame, [0, 10], [16, 0], { extrapolateRight: "clamp" });

                return (
                  <div key={block.key || idx}>
                    {renderCard(block, opacity, translateY)}
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
                    WebkitBackdropFilter: "blur(10px)",
                    border: "1px solid rgba(255, 255, 255, 0.06)",
                    borderRadius: 18,
                    padding: "22px 26px",
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
                      width: idx % 2 === 0 ? "72%" : "60%",
                      background: `rgba(255, 255, 255, ${pulseOpacity})`,
                      boxShadow: "0 0 12px rgba(255, 255, 255, 0.12)",
                    }}
                  />
                  <div
                    style={{
                      height: 14,
                      borderRadius: 4,
                      width: idx % 2 === 0 ? "40%" : "50%",
                      background: `rgba(255, 255, 255, ${pulseOpacity * 0.55})`,
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
              WebkitBackdropFilter: "blur(20px)",
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