#!/usr/bin/env python3
"""
Generate a short (15-30s spoken) horoscope for a given sign/element via OpenAI.

Usage:
    # OPENAI_API_KEY is read from a .env file in the project root (see .env.example),
    # or from an already-exported shell environment variable — either works.
    python generate_horoscope.py --sign Sagittarius --element fire

    # Offline test of prompt + validation logic, no API call:
    python generate_horoscope.py --sign Sagittarius --element fire --dry-run

Prints JSON: {sign, element, text, word_count} to stdout.
Retries up to MAX_RETRIES times if the model's output falls outside the
target word-count band (spoken 15-30s ≈ 40-70 words at a measured pace).
"""
import argparse
import json
import os
import sys

from pathlib import Path
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)  # reads .env in project root
except ImportError:
    pass  # dotenv not installed — falls back to whatever's already in the shell env

MIN_WORDS = 40
MAX_WORDS = 70
MAX_RETRIES = 3

SYSTEM_PROMPT = """You write short daily horoscopes for a mystical, elemental-creature \
themed astrology brand. Voice: elegant, mysterious, a little cryptic — like an oracle, \
not a lifestyle influencer. Never use emojis, hashtags, or exclamation points. Speak \
directly to the reader as "you". Ground the reading in one clear, concrete piece of \
guidance or reflection for the day — avoid vague filler like "great things are coming".

Output ONLY the horoscope text itself. No preamble, no sign-off, no quotation marks."""

def build_user_prompt(sign: str, element: str) -> str:
    return (
        f"Write today's horoscope for {sign} ({element} sign). "
        f"Target length: {MIN_WORDS}-{MAX_WORDS} words — this will be read aloud "
        f"in 15-30 seconds, so keep sentences spoken-friendly, not dense or list-like."
    )


def call_openai(sign: str, element: str) -> str:
    from openai import OpenAI
    client = OpenAI()  # reads OPENAI_API_KEY from env
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(sign, element)},
        ],
        temperature=0.9,
    )
    return resp.choices[0].message.content.strip()


def mock_response(sign: str, element: str) -> str:
    # Used only with --dry-run, to exercise the validation/retry logic offline.
    return (
        f"The {element} in you is restless today, {sign}. Something you have been "
        f"circling for weeks is finally asking for a decision, not more thought. "
        f"Trust the instinct that arrives before the doubt does. A conversation you "
        f"have been avoiding will be easier than you expect — begin it before noon, "
        f"while your nerve is still steady and the day has not yet worn you down."
    )


def generate(sign: str, element: str, dry_run: bool) -> dict:
    fetch = mock_response if dry_run else call_openai

    last_text = None
    for attempt in range(1, MAX_RETRIES + 1):
        text = fetch(sign, element)
        word_count = len(text.split())
        last_text = text
        if MIN_WORDS <= word_count <= MAX_WORDS:
            return {"sign": sign, "element": element, "text": text, "word_count": word_count}
        print(
            f"[attempt {attempt}] word_count={word_count} outside "
            f"[{MIN_WORDS},{MAX_WORDS}], retrying...",
            file=sys.stderr,
        )

    # Exhausted retries — return the last attempt anyway, flagged, rather than
    # silently failing the whole pipeline run over a word-count miss.
    return {
        "sign": sign,
        "element": element,
        "text": last_text,
        "word_count": len(last_text.split()),
        "warning": "word count out of target band after max retries",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sign", required=True)
    parser.add_argument("--element", required=True, choices=["fire", "earth", "air", "water"])
    parser.add_argument("--dry-run", action="store_true", help="skip the API call, use a mock response")
    args = parser.parse_args()

    if not args.dry_run and not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set. Use --dry-run to test without an API key.", file=sys.stderr)
        sys.exit(1)

    result = generate(args.sign, args.element, args.dry_run)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
