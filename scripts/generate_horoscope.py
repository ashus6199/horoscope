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

SYSTEM_PROMPT = """You write daily horoscope videos for a data-driven Gen-Z astrology brand. \
You will output TWO parallel layers:
1. Concise, scannable ON-SCREEN CARD TEXT (summarized for quick reading on video cards).
2. Natural, conversational SPOKEN VOICEOVER NARRATION (spoken by TTS like a warm, smart friend in a podcast or conversation).

Voice for spoken narration: direct, conversational, narrative, smart-friend tone. \
CRITICAL RULE: NEVER speak the sign name (e.g. NEVER say "Sagittarius", "Leo", "Aries") in the spoken voiceover! \
The sign name is already rendered in large text on the video header. Speak directly to the viewer as "you", "your sun", or "your energy". \
Never sound like reading out bullet points or raw labels (e.g. NEVER speak "Do: ... Don't: ..." or "Best energy: ..."). \
Instead, speak naturally in full sentences (e.g., "Whatever path you've chosen, take a second to re-evaluate it today...", \
"You'll vibe best with Aries energy today to amplify your momentum...").

Never use emojis, exclamation points, or vague filler like "reflection and letting go" or "feeling emotional adjustments". \
Never manufacture clock urgency ("before it's too late").

You will be given today's REAL astronomical transit data and REAL whole-sign aspect compatibility for the target sign. \
Use only what's given — do not invent any transit or aspect beyond it.

Output a JSON object with exactly these fields:
- "card_hook" (5-8 words): concise on-screen card text stating the real transit fact in curious language.
- "spoken_hook" (10-16 words): natural conversational voiceover introducing today's astronomical transit for the viewer (do NOT state the sign name).
- "power_focus" (2-5 words): the concrete power focus for today (e.g., "Finish open tasks", "Set boundaries early").
- "power_color" (1-2 words): the power color to wear/harness today (e.g., "Forest green", "Deep navy").
- "spoken_context" (12-20 words): natural conversational voiceover explaining the Moon's influence and practical focus/power color.
- "sharp_do" (3-7 words): the specific DO action for today (e.g., "Ship Monday's project").
- "sharp_dont" (3-7 words): the specific DON'T action for today (e.g., "Re-open old arguments").
- "spoken_sharp_line" (12-22 words): natural conversational voiceover giving the specific practical advice/directive in a warm narrative voice.
- "spoken_compatibility_line" (12-20 words): natural conversational voiceover explaining which sign to connect with and which to handle with care.
- "caption" (40-70 words): atmospheric post caption text with 3-5 lowercase hashtags at the end.

Output ONLY the JSON object. No markdown fences, no preamble."""


def build_transit_context(moon_sign, moon_phase_label, retrogrades, sign, compatibility) -> str:
    facts = []
    if sign:
        facts.append(f"Target Account Sign: {sign}.")
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
        except Exception as e:
            print(f"[WARNING] Could not auto-fetch transits ({e}); proceeding without them.", file=sys.stderr)

    transit_context = build_transit_context(moon_sign, moon_phase_label, retrogrades, args.sign, compatibility)
    result = generate(args.sign, args.element, transit_context, args.dry_run)
    result["transit_context"] = transit_context
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()