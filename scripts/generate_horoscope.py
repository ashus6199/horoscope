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
from datetime import datetime, timezone

from pathlib import Path
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

from get_transits import aspect_between

MIN_SPOKEN_WORDS = 85
MAX_SPOKEN_WORDS = 145
MAX_RETRIES = 3

SYSTEM_PROMPT = """\
You write daily horoscope videos for a data-driven Gen-Z astrology brand. \
You will output TWO parallel layers across 5 progressive beats:
1. Concise, scannable ON-SCREEN CARD TEXT (summarized for quick reading on 5 sequential video cards).
2. Natural, conversational SPOKEN VOICEOVER NARRATION (spoken by TTS like a warm, smart friend for a 50-second video).

=== 5-BEAT NARRATIVE ARC (MANDATORY) ===
Every daily reading follows ONE continuous 5-beat story arc anchored to today's real transit data:
- Beat 1 (Hook): Ground in today's main astronomical event / Moon transit — what the sky is doing.
- Beat 2 (Sky Weather): Deepen the astronomical context using active retrogrades or moon phase details (e.g., active retrograde progress or transit atmospheric mood).
- Beat 3 (Focus): Connect the sky cause to the viewer's daily mental focus using "Because of that..." or similar.
- Beat 4 (Insight): An observational sharp DO & DON'T line — NOT a preachy directive ("Finishing something today will feel better than starting it").
- Beat 5 (Reflection & Compatibility): Ask a short, engaging journal reflection question AND connect to relational sign energy (`harmonious_pick` & `friction_pick`).

=== VOICE RULES ===
- Direct, conversational, narrative, smart-friend tone.
- CRITICAL: NEVER speak the viewer's target sun sign name (e.g. NEVER say "Sagittarius" when writing for Sagittarius). \
  The viewer's sign name is already rendered in large text on the video header. Speak directly to the viewer as "you", "your sun", or "your energy".
- MANDATORY COMPATIBILITY SIGN NAMES: In `spoken_compatibility_line`, you MUST explicitly speak the exact names of the `harmonious_pick` sign (e.g. "Aries") and `friction_pick` sign (e.g. "Gemini") provided in the transit data. Do NOT substitute generic phrases like "those who share your passion" or "fire signs".
- JOURNAL REFLECTION QUESTION: The `reflection_question` field MUST be a short, engaging self-reflection question (e.g., "What are you holding back from finishing today?") that prompts comments and saves.
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
- COMPATIBILITY ACCURACY: You MUST use exactly the `harmonious_pick` and `friction_pick` signs provided in the transit data for `spoken_compatibility_line`. You MUST state both sign names explicitly in the voiceover.
- Use ONLY the transit and compatibility data given — do not invent any transit or aspect beyond it.

=== EVENT-AWARE ANCHORING ===
If "event_alert" data is provided in the transit context, the spoken_hook and card_hook MUST anchor to that event \
(e.g. "Full Moon energy is building..." or "Mercury stations retrograde today..."). \
The event becomes the central theme that the other beats connect back to.

=== OUTPUT FORMAT ===
Output a JSON object with exactly these fields:
- "card_hook" (5-8 words): concise on-screen card text stating today's main transit fact.
- "spoken_hook" (15-22 words): natural voiceover introducing today's transit (do NOT state the viewer's sign name).
- "card_sky_weather" (4-8 words): concise on-screen text for planetary sky weather or retrograde status.
- "spoken_sky_weather" (15-22 words): natural voiceover elaborating on today's sky weather or planetary motion.
- "power_focus" (2-5 words): the concrete power focus for today.
- "power_color" (1-2 words): the power color for today (select from the allowed element palette).
- "spoken_context" (20-28 words): natural voiceover connecting sky weather to the daily focus theme.
- "sharp_do" (3-7 words): specific DO observation.
- "sharp_dont" (3-7 words): specific DON'T observation.
- "spoken_sharp_line" (20-28 words): observational voiceover insight.
- "spoken_compatibility_line" (20-28 words): voiceover explaining harmonious and friction sign compatibility.
- "reflection_question" (5-10 words): short, engaging self-reflection question for viewer comments/saves.
- "spoken_reflection" (18-26 words): voiceover introducing and explicitly speaking the reflection_question word-for-word, followed by a closing phrase ONLY in the voiceover (e.g., "Take a pause and think about it.").
- "caption" (40-70 words): atmospheric post caption text with 3-5 lowercase hashtags at the end.

Output ONLY the JSON object. No markdown fences, no preamble."""


def build_transit_context(moon_sign, moon_phase_label, retrogrades, sign, compatibility, event_alert=None, sky_weather=None) -> str:
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
    if sky_weather and sky_weather.get("summary"):
        facts.append(f"Sky Weather / Retrogrades: {sky_weather['summary']}.")
    elif retrogrades:
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


HISTORY_FILE = Path(__file__).resolve().parent.parent / "data" / "script_history.json"


def load_script_history(sign: str) -> list[dict]:
    if not HISTORY_FILE.exists():
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            data = json.load(f)
            return data.get(sign.lower(), [])[-5:]
    except Exception:
        return []


def save_script_history(sign: str, result: dict):
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {}
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r") as f:
                data = json.load(f)
        except Exception:
            data = {}

    sign_key = sign.lower()
    sign_history = data.get(sign_key, [])
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = {
        "date": now_iso,
        "power_focus": result.get("power_focus", ""),
        "power_color": result.get("power_color", ""),
        "sharp_do": result.get("sharp_do", ""),
        "sharp_dont": result.get("sharp_dont", ""),
        "spoken_sharp_line": result.get("spoken_sharp_line", ""),
        "reflection_question": result.get("reflection_question", ""),
        "spoken_reflection": result.get("spoken_reflection", ""),
    }
    sign_history.append(entry)
    data[sign_key] = sign_history[-10:]

    try:
        with open(HISTORY_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"[WARNING] Could not save script history ({e})", file=sys.stderr)


def tokenize_words(text: str) -> set[str]:
    words = re.findall(r'\b[a-z]{3,}\b', text.lower())
    stopwords = {
        "the", "and", "for", "that", "this", "with", "you", "your", "today",
        "from", "have", "will", "what", "are", "about", "more", "into", "than"
    }
    return set(w for w in words if w not in stopwords)


def is_too_similar(candidate: dict, history: list[dict]) -> bool:
    if not history:
        return False

    cand_focus = tokenize_words(candidate.get("power_focus", "") + " " + candidate.get("sharp_do", ""))
    cand_question = tokenize_words(candidate.get("reflection_question", ""))

    for past in history:
        past_focus = tokenize_words(past.get("power_focus", "") + " " + past.get("sharp_do", ""))
        past_question = tokenize_words(past.get("reflection_question", ""))

        # Check focus/action word overlap
        if cand_focus and past_focus:
            intersection = cand_focus.intersection(past_focus)
            union = cand_focus.union(past_focus)
            jaccard = len(intersection) / len(union) if union else 0
            if jaccard > 0.35:
                print(f"[RETRY CHECK] Focus '{candidate.get('power_focus')}' shares too much overlap with past focus '{past.get('power_focus')}' (Jaccard: {jaccard:.2f})", file=sys.stderr)
                return True

        # Check reflection question word overlap
        if cand_question and past_question:
            q_intersection = cand_question.intersection(past_question)
            q_union = cand_question.union(past_question)
            q_jaccard = len(q_intersection) / len(q_union) if q_union else 0
            if q_jaccard > 0.40:
                print(f"[RETRY CHECK] Question '{candidate.get('reflection_question')}' shares too much overlap with past question '{past.get('reflection_question')}' (Jaccard: {q_jaccard:.2f})", file=sys.stderr)
                return True

    return False


ELEMENT_PALETTES = {
    "fire": ["Warm Coral", "Gold", "Crimson", "Ruby", "Scarlet", "Amber", "Burnt orange", "Rust"],
    "earth": ["Forest green", "Emerald", "Sage", "Terracotta", "Olive", "Bronze", "Copper"],
    "air": ["Electric Violet", "Cyan", "Lavender", "Midnight blue", "Sky blue", "Silver"],
    "water": ["Deep Indigo", "Teal", "Aquamarine", "Deep navy", "Turquoise", "Plum"],
}


def build_user_prompt(sign: str, element: str, transit_context: str, history: list[dict] = None) -> str:
    allowed_colors = ", ".join(ELEMENT_PALETTES.get(element.lower(), ELEMENT_PALETTES["fire"]))
    prompt = (
        f"Write today's 6-beat horoscope card for {sign} ({element} sign).\n\n"
        f"Today's real transit and compatibility data: {transit_context}\n\n"
        f"IMPORTANT: For power_color, you MUST select a color from the {element.upper()} palette: {allowed_colors}."
    )
    if history:
        avoid_themes = []
        avoid_questions = []
        avoid_colors = []
        for item in history:
            if item.get("power_focus"):
                avoid_themes.append(f"- Focus: '{item.get('power_focus')}', DO: '{item.get('sharp_do')}'")
            if item.get("reflection_question"):
                avoid_questions.append(f"- Question: '{item.get('reflection_question')}'")
            if item.get("power_color"):
                avoid_colors.append(item.get("power_color"))

        prompt += (
            f"\n\n=== RECENT READINGS FOR {sign.upper()} (LAST 5 DAYS) ===\n"
            f"Do NOT repeat, paraphrase, or reuse any of the following recent themes, questions, or colors:\n"
        )
        if avoid_themes:
            prompt += "Recent Themes & Actions:\n" + "\n".join(avoid_themes) + "\n"
        if avoid_questions:
            prompt += "Recent Reflection Questions:\n" + "\n".join(avoid_questions) + "\n"
        if avoid_colors:
            prompt += f"Recent Colors Used: {', '.join(set(avoid_colors))}\n"
        prompt += "\nYou MUST generate a completely original focus theme, fresh DO/DON'T pair, and unique reflection question today."
    return prompt


def call_openai(sign: str, element: str, transit_context: str, history: list[dict] = None) -> dict:
    from openai import OpenAI
    import time
    client = OpenAI()

    last_err = None
    for attempt in range(1, 4):
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": build_user_prompt(sign, element, transit_context, history)},
                ],
                temperature=0.85,
                timeout=30.0,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            last_err = e
            print(f"[WARNING] OpenAI API attempt {attempt} failed ({e}); retrying in {attempt * 2}s...", file=sys.stderr)
            time.sleep(attempt * 2)

    print(f"[ERROR] All OpenAI API attempts failed: {last_err}", file=sys.stderr)
    raise last_err


def mock_response(sign: str, element: str, transit_context: str) -> dict:
    # Used only with --dry-run, to exercise validation/retry logic offline.
    palette = ELEMENT_PALETTES.get(element.lower(), ELEMENT_PALETTES["fire"])
    color_idx = sum(ord(c) for c in f"{sign}{transit_context}") % len(palette)
    power_color = palette[color_idx]

    return {
        "card_hook": f"Waning Moon in Taurus tests your {element} energy.",
        "spoken_hook": "Today's waning Moon in Taurus forms a challenging angle to your sun sign today.",
        "card_sky_weather": "Mercury in steady motion",
        "spoken_sky_weather": "With current sky transits highlighting practical priorities, steady grounded momentum is favored.",
        "power_focus": "Finish open tasks",
        "power_color": power_color,
        "spoken_context": "This steady energy is asking you to ground your restless thoughts today into one priority before expanding outward.",
        "sharp_do": "Finish active tasks",
        "sharp_dont": "Re-open old arguments",
        "spoken_sharp_line": "Whatever project you started earlier this week, push to finish it today rather than starting something completely new.",
        "reflection_question": "What priority are you avoiding finishing today?",
        "spoken_compatibility_line": "You will vibe best with Aries energy today, but handle Gemini with extra care.",
        "spoken_reflection": "As today closes, ask yourself: what priority are you avoiding finishing today? Take a pause and think about it.",
        "caption": (
            f"Under a waning Taurus moon, the {element} in you meets earth that refuses to "
            f"hurry. What already has momentum wants your attention now, not the next spark. "
            f"#{sign.lower()} #dailyhoroscope #moonintaurus"
        ),
    }


def spoken_word_count(result: dict) -> int:
    return sum(
        len(result.get(k, "").split())
        for k in ("spoken_hook", "spoken_sky_weather", "spoken_context", "spoken_sharp_line", "spoken_compatibility_line", "spoken_reflection")
    )


def generate(sign: str, element: str, transit_context: str, dry_run: bool) -> dict:
    history = load_script_history(sign)
    fetch = (lambda s, e, tc, h=None: mock_response(s, e, tc)) if dry_run else call_openai

    last_result = None
    for attempt in range(1, MAX_RETRIES + 1):
        result = fetch(sign, element, transit_context, history)
        word_count = spoken_word_count(result)
        last_result = result

        if not dry_run and is_too_similar(result, history):
            print(f"[attempt {attempt}] candidate script is too similar to recent history for {sign}, retrying...", file=sys.stderr)
            continue

        if MIN_SPOKEN_WORDS <= word_count <= MAX_SPOKEN_WORDS:
            result["sign"] = sign
            result["element"] = element
            result["word_count"] = word_count
            save_script_history(sign, result)
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
    if not dry_run:
        save_script_history(sign, last_result)
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
    parser.add_argument("--date", default=None, help="Override date (YYYY-MM-DD)")
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
            trans_cmd = [sys.executable, str(transits_script), "--sign", args.sign]
            if args.date:
                trans_cmd.extend(["--date", args.date])
            out = subprocess.run(
                trans_cmd,
                capture_output=True, text=True, check=True,
            )
            transits = json.loads(out.stdout)
            moon_sign = transits["moon_sign"]
            moon_phase_label = transits["moon_phase_label"]
            retrogrades = transits["retrogrades"]
            compatibility = transits.get("compatibility")
            event_alert = transits.get("event_alert")
            sky_weather = transits.get("sky_weather")
        except Exception as e:
            print(f"[WARNING] Could not auto-fetch transits ({e}); proceeding without them.", file=sys.stderr)

    transit_context = build_transit_context(moon_sign, moon_phase_label, retrogrades, args.sign, compatibility, event_alert, sky_weather)
    result = generate(args.sign, args.element, transit_context, args.dry_run)
    result["transit_context"] = transit_context
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()