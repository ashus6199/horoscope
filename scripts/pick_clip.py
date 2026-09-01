#!/usr/bin/env python3
"""
Pick the least-recently-used clip for a given element from manifest.json.
Usage:
    python pick_clip.py --element fire --manifest ../manifest/manifest.json
    python pick_clip.py --element fire --manifest ../manifest/manifest.json --mark-used

Prints the chosen clip as JSON to stdout. With --mark-used, also writes
today's date back into that clip's last_used field in the manifest file
(so the next run picks a different clip).
"""
import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path


def load_manifest(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)


def save_manifest(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def pick_clip(manifest: dict, element: str) -> dict:
    candidates = [c for c in manifest["clips"] if c["element"] == element]
    if not candidates:
        raise ValueError(f"No clips found for element '{element}' in manifest")

    # Never-used clips (last_used is None) sort first, then oldest last_used.
    def sort_key(clip):
        if clip["last_used"] is None:
            return (0, "")
        return (1, clip["last_used"])

    candidates.sort(key=sort_key)
    return candidates[0]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--element", required=True, choices=["fire", "earth", "air", "water"])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--mark-used", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    chosen = pick_clip(manifest, args.element)

    if args.mark_used:
        today = date.today().isoformat()
        for clip in manifest["clips"]:
            if clip["id"] == chosen["id"]:
                clip["last_used"] = today
        save_manifest(args.manifest, manifest)
        chosen["last_used"] = today  # reflect in printed output too

    print(json.dumps(chosen, indent=2))


if __name__ == "__main__":
    main()
