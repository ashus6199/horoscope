#!/usr/bin/env python3
"""
Pick the next sequential clip for a given element from the assets folder.
If the next clip (e.g. fire_003) doesn't exist, it loops back to fire_001.

Usage:
    python pick_clip.py --element fire --manifest ../manifest/manifest.json
    python pick_clip.py --element fire --manifest ../manifest/manifest.json --mark-used
"""
import argparse
import json
import re
from datetime import date
from pathlib import Path


def load_manifest(path: Path) -> dict:
    if path.exists():
        with open(path, "r") as f:
            return json.load(f)
    return {"clips": []}


def save_manifest(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--element", required=True, choices=["fire", "earth", "air", "water"])
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--mark-used", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)

    # 1. Find the most recently used clip in the manifest for this element
    element_clips = [c for c in manifest.get("clips", []) if c.get("element") == args.element and c.get("last_used")]
    # sort by last_used descending
    element_clips.sort(key=lambda c: c["last_used"], reverse=True)

    last_id = element_clips[0]["id"] if element_clips else f"{args.element}_000"

    # 2. Extract number
    match = re.search(r'_(\d+)$', last_id)
    last_num = int(match.group(1)) if match else 0
    next_num = last_num + 1

    # 3. Check assets folder for the next number
    repo_root = Path(__file__).resolve().parent.parent
    assets_dir = repo_root / "remotion" / "public" / "assets"

    next_id = f"{args.element}_{next_num:03d}"
    next_filename = f"{next_id}.mp4"
    next_path = assets_dir / next_filename

    if next_path.exists():
        chosen_id = next_id
        chosen_filename = next_filename
    else:
        # Go back to 1
        chosen_id = f"{args.element}_001"
        chosen_filename = f"{chosen_id}.mp4"
        if not (assets_dir / chosen_filename).exists():
            raise ValueError(f"Could not find fallback '{chosen_filename}' in {assets_dir}")

    chosen_clip = {
        "id": chosen_id,
        "element": args.element,
        "filename": chosen_filename,
        "last_used": None
    }

    if args.mark_used:
        today = date.today().isoformat()
        chosen_clip["last_used"] = today

        # update manifest
        found = False
        for c in manifest.get("clips", []):
            if c.get("id") == chosen_id:
                c["last_used"] = today
                found = True

        if not found:
            if "clips" not in manifest:
                manifest["clips"] = []
            manifest["clips"].append(chosen_clip)

        save_manifest(args.manifest, manifest)

    print(json.dumps(chosen_clip, indent=2))


if __name__ == "__main__":
    main()
