#!/usr/bin/env python3
"""
Generate a progressive-disclosure daily horoscope card for a given sign via OpenAI.

Usage:
    python generate_horoscope.py --sign Sagittarius --element fire
    python generate_horoscope.py --sign Sagittarius --element fire --dry-run

Prints JSON: {sign, element, card_lines: [...], caption, hashtags, word_count}
card_lines are revealed on screen in order, each staying visible as the next
appears (nothing is replaced) — see AGENTS.md for the reveal timing.
"""
import argparse
import json
import os
import sys

from pathlib import Path
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

from get_transits import aspect_between

MIN_SPOKEN_WORDS = 35
MAX_SPOKEN_WORDS = 90
MAX_RETRIES = 3

SYSTEM_PROMPT = """\
You write daily horoscope videos for a data-driven Gen-Z astrology brand. \
You will output TWO parallel layers:
1. Concise, scannable ON-SCREEN CARD TEXT (summarized for quick reading on video cards).
2. Natural, conversational SPOKEN VOICEOVER NARRATION (spoken by TTS like a warm, smart friend).

=== NARRATIVE ARC (MANDATORY) ===
Every daily reading follows ONE continuous story arc anchored to a SINGLE overarching daily theme \
derived from today's real transit data. The 4 spoken beats must read as one connected thought, \
NOT as 4 separate index cards. Use mandatory logical transitions between beats:
- Beat 1 (Cause): Ground in today's real transit — what the sky is doing and the friction or flow it creates.
- Beat 2 (Focus): Connect the cause to the viewer's daily mental focus using "Because of that..." or similar.
- Beat 3 (Insight): An observational sharp line — NOT a command. Phrase it as an observation \
  ("Finishing something today will feel better than starting it") NOT a directive ("Go finish your project").
- Beat 4 (Circle): Connect to relational sign energy using "Because of that same..." or similar.

=== VOICE RULES ===
- Direct, conversational, narrative, smart-friend tone.
- CRITICAL: NEVER speak the sign name (e.g. NEVER say "Sagittarius", "Leo", "Aries") in the spoken voiceover. \
  The sign name is already rendered in large text on the video header. Speak directly to the viewer as "you", "your sun", or "your energy".
- Never sound like reading out bullet points or raw labels (e.g. NEVER speak "Do: ... Don't: ..." or "Best energy: ...").
- Never use emojis, exclamation points, or vague filler like "reflection and letting go".
- Never manufacture clock urgency ("before it's too late").

=== STRICT CONTENT RULES ===
- NO COLD-READING FABRICATIONS: Never invent specific personal details about the viewer's life — \
  no specific days ("Monday's draft"), times ("around lunch"), objects, or situations not in the transit data. \
  Ground in universal states ("finishing what's already in motion", "grounding into one priority").
- OBSERVATIONAL FRAMING ONLY: No preachy command imperatives ("Do X!", "Don't do Y!"). \
  Keep insights observational ("X will feel better than Y", "Starting new things carries more friction today").
- POWER COLOR AS DESIGN ACCENT ONLY: The power_color field is rendered visually as a color swatch on screen. \
  Do NOT speak the color name as a superstitious claim in the voiceover ("wear forest green for luck"). \
  The spoken_context beat should focus on the power_focus theme, not the color.
- Use ONLY the transit and compatibility data given — do not invent any transit or aspect beyond it.

=== EVENT-AWARE ANCHORING ===
If "event_alert" data is provided in the transit context, the spoken_hook and card_hook MUST anchor to that event \
(e.g. "Full Moon energy is building..." or "Mercury stations retrograde today..."). \
The event becomes the central theme that the other 3 beats connect back to.

=== OUTPUT FORMAT ===
Output a JSON object with exactly these fields:
- "card_hook" (5-8 words): concise on-screen card text stating the real transit fact in curious language.
- "spoken_hook" (10-16 words): natural conversational voiceover introducing today's transit (do NOT state the sign name).
- "power_focus" (2-5 words): the concrete power focus for today (e.g., "Ground into one priority").
- "power_color" (1-2 words): the power color for today (e.g., "Forest green", "Deep navy").
- "spoken_context" (12-20 words): natural conversational voiceover connecting the transit cause to the daily focus theme.
- "sharp_do" (3-7 words): the specific DO observation for today.
- "sharp_dont" (3-7 words): the specific DON'T observation for today.
- "spoken_sharp_line" (12-22 words): natural observational voiceover — phrased as an insight, not a command.
- "spoken_compatibility_line" (12-20 words): natural conversational voiceover explaining which sign's energy lands easier and which creates friction.
- "caption" (40-70 words): atmospheric post caption text with 3-5 lowercase hashtags at the end.

Output ONLY the JSON object. No markdown fences, no preamble."""


def build_transit_context(moon_sign, moon_phase_label, retrogrades, sign, compatibility, event_alert=None) -> str:
    facts = []
    if sign:
        facts.append(f"Target Account Sign: {sign}.")
    if event_alert:
        facts.append(f"event_alert (TIER {event_alert.get('tier', '?')}): {event_alert.get('label', '')}. "
                      f"Type: {event_alert.get('type', '')}. "
                      "Anchor the hook and central theme to this event.")
    if moon_sign:
        phase_bit = f", {moon_phase_label}" if moon_phase_label else ""
        facts.append(f"Today's Moon is in {moon_sign}{phase_bit}.")
    if retrogrades:
        verb = "is" if len(retrogrades) == 1 else "are"
        facts.append(f"{', '.join(retrogrades)} {verb} currently retrograde.")
    if moon_sign and sign:
        own_aspect = aspect_between(sign, moon_sign)
        facts.append(f"Today's Moon forms a {own_aspect} aspect to this sun sign.")
    if compatibility and compatibility.get("harmonious_pick"):
        facts.append(f"harmonious_pick (aligns smoothly with this sun sign): {compatibility['harmonious_pick']}")
    if compatibility and compatibility.get("friction_pick"):
        facts.append(f"friction_pick (creates tension for this sun sign): {compatibility['friction_pick']}")
    if not facts:
        return "No specific transit data available today — write a grounded reading without referencing any transit."
    return " ".join(facts)


def build_user_prompt(sign: str, element: str, transit_context: str) -> str:
    return (
        f"Write today's horoscope card for {sign} ({element} sign).\n\n"
        f"Today's real transit and compatibility data: {transit_context}"
    )


def call_openai(sign: str, element: str, transit_context: str) -> dict:
    from openai import OpenAI
    client = OpenAI()
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(sign, element, transit_context)},
        ],
        temperature=0.85,
    )
    return json.loads(resp.choices[0].message.content)


def mock_response(sign: str, element: str, transit_context: str) -> dict:
    # Used only with --dry-run, to exercise validation/retry logic offline.
    return {
        "card_hook": f"Waning Moon in Taurus tests your {element} energy.",
        "spoken_hook": "Today's waning Moon in Taurus forms a challenging angle to your sun.",
        "power_focus": "Finish open tasks",
        "power_color": "Forest green",
        "spoken_context": "This steady earth placement is asking you to ground your restless energy today. Focus on clearing your open tasks and wear forest green.",
        "sharp_do": "Ship Monday's project",
        "sharp_dont": "Re-open old arguments",
        "spoken_sharp_line": "Whatever project you started earlier this week, push to finish it today. And if old disagreements bubble up, don't re-open them.",
        "spoken_compatibility_line": "You will vibe best with Aries energy today to amplify your momentum, but handle Gemini with extra care to avoid static.",
        "caption": (
            f"Under a waning Taurus moon, the {element} in you meets earth that refuses to "
            f"hurry. What already has momentum wants your attention now, not the next spark. "
            f"#{sign.lower()} #dailyhoroscope #moonintaurus"
        ),
    }


def spoken_word_count(result: dict) -> int:
    return sum(
        len(result.get(k, "").split())
        for k in ("spoken_hook", "spoken_context", "spoken_sharp_line", "spoken_compatibility_line")
    )


def generate(sign: str, element: str, transit_context: str, dry_run: bool) -> dict:
    fetch = mock_response if dry_run else call_openai

    last_result = None
    for attempt in range(1, MAX_RETRIES + 1):
        result = fetch(sign, element, transit_context)
        word_count = spoken_word_count(result)
        last_result = result
        if MIN_SPOKEN_WORDS <= word_count <= MAX_SPOKEN_WORDS:
            result["sign"] = sign
            result["element"] = element
            result["word_count"] = word_count
            return result
        print(
            f"[attempt {attempt}] spoken word_count={word_count} outside "
            f"[{MIN_SPOKEN_WORDS},{MAX_SPOKEN_WORDS}], retrying...",
            file=sys.stderr,
        )

    last_result["sign"] = sign
    last_result["element"] = element
    last_result["word_count"] = spoken_word_count(last_result)
    last_result["warning"] = "spoken word count out of target band after max retries"
    return last_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sign", required=True)
    parser.add_argument("--element", required=True, choices=["fire", "earth", "air", "water"])
    parser.add_argument("--moon-sign", default=None, help="Override moon sign instead of computing it live")
    parser.add_argument("--moon-phase-label", default=None)
    parser.add_argument("--retrogrades", default="", help="Comma-separated list, e.g. 'Mercury,Venus'")
    parser.add_argument("--no-auto-transits", action="store_true",
                         help="Skip calling get_transits.py automatically; use only --moon-sign/--retrogrades if given")
    parser.add_argument("--dry-run", action="store_true", help="skip the API call, use a mock response")
    args = parser.parse_args()

    if not args.dry_run and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set. Use --dry-run to test without an API key.", file=sys.stderr)
        sys.exit(1)

    moon_sign = args.moon_sign
    moon_phase_label = args.moon_phase_label
    retrogrades = [r.strip() for r in args.retrogrades.split(",") if r.strip()]
    compatibility = None
    event_alert = None

    if not moon_sign and not args.no_auto_transits:
        import subprocess
        transits_script = Path(__file__).resolve().parent / "get_transits.py"
        try:
            out = subprocess.run(
                [sys.executable, str(transits_script)],
                capture_output=True, text=True, check=True,
            )
            transits = json.loads(out.stdout)
            moon_sign = transits["moon_sign"]
            moon_phase_label = transits["moon_phase_label"]
            retrogrades = transits["retrogrades"]
            compatibility = transits.get("compatibility")
            event_alert = transits.get("event_alert")
        except Exception as e:
            print(f"[WARNING] Could not auto-fetch transits ({e}); proceeding without them.", file=sys.stderr)

    transit_context = build_transit_context(moon_sign, moon_phase_label, retrogrades, args.sign, compatibility, event_alert)
    result = generate(args.sign, args.element, transit_context, args.dry_run)
    result["transit_context"] = transit_context
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()