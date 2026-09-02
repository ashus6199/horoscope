#!/usr/bin/env python3
"""
Convert horoscope text to speech (edge-tts) and report the exact audio
duration *and* per-word timing (needed downstream so the Remotion render
can size itself to the audio and sync captions word-for-word to the
voiceover).

Usage:
    python generate_tts.py --text "..." --output ../output/sagittarius.mp3

    # Offline test of the duration-extraction step, no network call to
    # Microsoft's TTS service (not reachable from this sandbox). Produces
    # silent audio + evenly-spaced fake word timings so downstream code
    # (props building, Remotion) can still be exercised end-to-end:
    python generate_tts.py --text "..." --output ../output/sagittarius.mp3 --dry-run

Prints JSON to stdout:
    {
      output_path, duration_seconds, voice, rate, pitch, dry_run,
      word_timings: [{word, start, end}, ...]   # start/end in seconds
    }
"""
import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

# Tuned for "elegant, mysterious" — a measured pace and slightly lower pitch
# read as more deliberate/oracular than the default neutral delivery.
DEFAULT_VOICE = "en-GB-SoniaNeural"
DEFAULT_RATE = "-8%"
DEFAULT_PITCH = "-4Hz"

# edge-tts reports WordBoundary offsets/durations in 100-nanosecond units.
HNS_PER_SECOND = 10_000_000


async def synthesize(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> list[dict]:
    """Streams audio to output_path and collects word-level timings as it
    goes, via edge-tts's WordBoundary events. Returns a list of
    {word, start, end} dicts with start/end in seconds."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    word_timings: list[dict] = []

    with open(output_path, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / HNS_PER_SECOND
                end = (chunk["offset"] + chunk["duration"]) / HNS_PER_SECOND
                word_timings.append({
                    "word": chunk["text"],
                    "start": round(start, 3),
                    "end": round(end, 3),
                })

    return word_timings


def synthesize_silence_stub(text: str, output_path: Path) -> list[dict]:
    # Dry-run stand-in: silent audio roughly matching expected spoken length
    # (~2.5 words/sec at this rate), so downstream duration + caption-timing
    # logic can be tested without a real network call. Word timings are
    # evenly spaced across the stub duration — not real speech timing, but
    # enough to exercise the same schema/props path as production.
    words = text.split()
    word_count = len(words)
    approx_seconds = max(1.0, word_count / 2.5)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", str(approx_seconds), str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    per_word = approx_seconds / word_count if word_count else 0.0
    word_timings = []
    for i, w in enumerate(words):
        start = round(i * per_word, 3)
        end = round(start + per_word * 0.85, 3)  # small gap between words
        word_timings.append({"word": w, "start": start, "end": end})

    return word_timings


def get_duration_seconds(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(path),
        ],
        capture_output=True, text=True, check=True,
    )
    return round(float(result.stdout.strip()), 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--voice", default=DEFAULT_VOICE)
    parser.add_argument("--rate", default=DEFAULT_RATE)
    parser.add_argument("--pitch", default=DEFAULT_PITCH)
    parser.add_argument("--dry-run", action="store_true", help="generate silence instead of calling edge-tts")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        word_timings = synthesize_silence_stub(args.text, args.output)
    else:
        word_timings = asyncio.run(
            synthesize(args.text, args.voice, args.rate, args.pitch, args.output)
        )

    duration = get_duration_seconds(args.output)

    print(json.dumps({
        "output_path": str(args.output),
        "duration_seconds": duration,
        "voice": args.voice,
        "rate": args.rate,
        "pitch": args.pitch,
        "dry_run": args.dry_run,
        "word_timings": word_timings,
    }, indent=2))


if __name__ == "__main__":
    main()