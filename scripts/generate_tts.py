#!/usr/bin/env python3
"""
Convert horoscope text to speech (edge-tts) and report the exact audio duration
(needed downstream so the Remotion render can size itself to the audio).

Usage:
    python generate_tts.py --text "..." --output ../output/sagittarius.mp3

    # Offline test of the duration-extraction step, no network call to
    # Microsoft's TTS service (not reachable from this sandbox):
    python generate_tts.py --text "..." --output ../output/sagittarius.mp3 --dry-run

Prints JSON: {output_path, duration_seconds, voice, rate, pitch} to stdout.
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


async def synthesize(text: str, voice: str, rate: str, pitch: str, output_path: Path) -> None:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(str(output_path))


def synthesize_silence_stub(text: str, output_path: Path) -> None:
    # Dry-run stand-in: silent audio roughly matching expected spoken length
    # (~2.5 words/sec at this rate), so downstream duration logic can be
    # tested without a real network call.
    word_count = len(text.split())
    approx_seconds = max(1.0, word_count / 2.5)
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=24000:cl=mono",
            "-t", str(approx_seconds), str(output_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


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
        synthesize_silence_stub(args.text, args.output)
    else:
        asyncio.run(synthesize(args.text, args.voice, args.rate, args.pitch, args.output))

    duration = get_duration_seconds(args.output)

    print(json.dumps({
        "output_path": str(args.output),
        "duration_seconds": duration,
        "voice": args.voice,
        "rate": args.rate,
        "pitch": args.pitch,
        "dry_run": args.dry_run,
    }, indent=2))


if __name__ == "__main__":
    main()
