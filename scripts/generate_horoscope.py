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

MIN_CARD_WORDS = 15
MAX_CARD_WORDS = 45
MAX_RETRIES = 3

SYSTEM_PROMPT = """You write daily horoscope cards for a data-driven astrology brand aimed at \
Gen Z. Voice: blunt, specific, direct, a little dry — like a smart friend giving practical guidance, \
not a fortune cookie. Never use emojis, exclamation points, or vague filler like "reflection and letting go", \
"feeling emotional adjustments", or "great things are coming". Never manufacture urgency (no "before it's too late", \
no specific clock times, no "this window closes") — the audience finds that manipulative and it costs trust. \
Speak directly to the reader as "you".

You will be given today's REAL astronomical transit data and a REAL computed compatibility \
result for the target sign below. Use only what's given — do not invent any transit, aspect, or planetary event \
beyond it.

Output a JSON object with exactly these fields:
- "hook" (5-10 words): states today's real transit fact plainly. Not mystical, just true.
- "context" (8-15 words): one sentence on what that placement means specifically for the target sign's energy today.
- "sharp_line" (6-14 words): THE ACTIONABLE TAKEAWAY. A sharp, concrete, actionable directive or practical advice \
for the target sign today — tell the reader specifically what practical move to make or what trap to avoid. Must be \
grounded and specific, never vague emotional fluff.
- "compatibility_line" (10-20 words): states how the target sign interacts with the given harmonious_pick sign \
(which aligns smoothly with the target sign) and friction_pick sign (which creates tension/static for the target sign). \
Must speak directly from the target sign's perspective (e.g., "Aries energy aligns smoothly with you today, while Gemini's pace creates static.").
- "caption" (40-70 words): the longer, more atmospheric flavor text for the post caption — this \
is where mystical, evocative language belongs (it does not belong in the card lines above). \
End it with 3-5 lowercase hashtags relevant to the sign and today's transit, space-separated, \
as part of this same string.

Output ONLY the JSON object. No markdown fences, no preamble."""


def build_transit_context(moon_sign, moon_phase_label, retrogrades, sign, compatibility) -> str:
    facts = []
    if sign:
        facts.append(f"Target Sign: {sign}.")
    if moon_sign:
        phase_bit = f", {moon_phase_label}" if moon_phase_label else ""
        facts.append(f"Today's Moon is in {moon_sign}{phase_bit}.")
    if retrogrades:
        verb = "is" if len(retrogrades) == 1 else "are"
        facts.append(f"{', '.join(retrogrades)} {verb} currently retrograde.")
    if moon_sign and sign:
        own_aspect = aspect_between(sign, moon_sign)
        facts.append(f"Today's Moon forms a {own_aspect} to {sign}.")
    if compatibility and compatibility.get("harmonious_pick"):
        facts.append(f"harmonious_pick (aligns smoothly with {sign}): {compatibility['harmonious_pick']}")
    if compatibility and compatibility.get("friction_pick"):
        facts.append(f"friction_pick (creates tension for {sign}): {compatibility['friction_pick']}")
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
        "hook": f"Today's Moon sits in Taurus, waning.",
        "context": f"This steady earth placement grounds your restless {element} energy today.",
        "sharp_line": f"Finish one open project before starting anything new, {sign}.",
        "compatibility_line": "Aries energy aligns smoothly with you today. Gemini's pace might create static.",
        "caption": (
            f"Under a waning Taurus moon, the {element} in you meets earth that refuses to "
            f"hurry. What already has momentum wants your attention now, not the next spark. "
            f"#{sign.lower()} #dailyhoroscope #moonintaurus"
        ),
    }


def card_word_count(result: dict) -> int:
    return sum(len(result.get(k, "").split()) for k in ("hook", "context", "sharp_line", "compatibility_line"))


def generate(sign: str, element: str, transit_context: str, dry_run: bool) -> dict:
    fetch = mock_response if dry_run else call_openai

    last_result = None
    for attempt in range(1, MAX_RETRIES + 1):
        result = fetch(sign, element, transit_context)
        word_count = card_word_count(result)
        last_result = result
        if MIN_CARD_WORDS <= word_count <= MAX_CARD_WORDS:
            result["sign"] = sign
            result["element"] = element
            result["word_count"] = word_count
            return result
        print(
            f"[attempt {attempt}] card word_count={word_count} outside "
            f"[{MIN_CARD_WORDS},{MAX_CARD_WORDS}], retrying...",
            file=sys.stderr,
        )

    last_result["sign"] = sign
    last_result["element"] = element
    last_result["word_count"] = card_word_count(last_result)
    last_result["warning"] = "card word count out of target band after max retries"
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