#!/usr/bin/env python3
"""
Orchestrator script for the horoscope video pipeline.

Steps executed:
 1. Pick clip via pick_clip.py
 2. Generate horoscope text via generate_horoscope.py
 3. Generate TTS audio via generate_tts.py & extract duration
 4. Stage audio & video clips into remotion/public/assets
 5. Output remotion/props.json with exact caption, audioPath, backgroundVideoPath, duration
 6. (Optional) Trigger remotion render if not --skip-render
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def run_command(cmd: list[str], cwd: Path | None = None) -> str:
    res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    return res.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description="Run full Horoscope video pipeline")
    parser.add_argument("--sign", required=True, help="Zodiac sign (e.g. Sagittarius)")
    parser.add_argument("--element", required=True, choices=["fire", "earth", "air", "water"])
    parser.add_argument("--manifest", type=Path, default=Path("manifest/manifest.json"))
    parser.add_argument("--mark-used", action="store_true", help="Mark selected clip as used in manifest")
    parser.add_argument("--dry-run", action="store_true", help="Use dry-run/mock responses")
    parser.add_argument("--skip-render", action="store_true", help="Prepare assets and props but skip Remotion render step")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--props-out", type=Path, default=Path("remotion/props.json"))
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    scripts_dir = repo_root / "scripts"
    remotion_dir = repo_root / "remotion"
    assets_dir = remotion_dir / "public" / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Step 1: Picking clip for element '{args.element}' ===")
    pick_cmd = [
        sys.executable, str(scripts_dir / "pick_clip.py"),
        "--element", args.element,
        "--manifest", str(args.manifest),
    ]
    if args.mark_used:
        pick_cmd.append("--mark-used")
    clip_output_json = run_command(pick_cmd, cwd=repo_root)
    clip_data = json.loads(clip_output_json)
    print(f"Picked clip: {clip_data.get('id')} ({clip_data.get('filename')})")

    print(f"\n=== Step 2: Generating Horoscope text for {args.sign} ===")
    horoscope_cmd = [
        sys.executable, str(scripts_dir / "generate_horoscope.py"),
        "--sign", args.sign,
        "--element", args.element,
    ]
    if args.dry_run or not os.environ.get("OPENAI_API_KEY"):
        print("[INFO] Using --dry-run for text generation (no OPENAI_API_KEY found or --dry-run passed)")
        horoscope_cmd.append("--dry-run")
    horoscope_output_json = run_command(horoscope_cmd, cwd=repo_root)
    horoscope_data = json.loads(horoscope_output_json)
    caption_text = horoscope_data["text"]
    print(f"Text ({horoscope_data.get('word_count')} words): {caption_text}")

    print(f"\n=== Step 3: Generating TTS Audio ===")
    audio_filename = f"{args.sign.lower()}.mp3"
    audio_output_path = args.output_dir / audio_filename
    tts_cmd = [
        sys.executable, str(scripts_dir / "generate_tts.py"),
        "--text", caption_text,
        "--output", str(audio_output_path),
    ]
    if args.dry_run:
        tts_cmd.append("--dry-run")
    tts_output_json = run_command(tts_cmd, cwd=repo_root)
    tts_data = json.loads(tts_output_json)
    duration_seconds = tts_data["duration_seconds"]
    print(f"Generated TTS audio: {audio_output_path} (Duration: {duration_seconds}s)")

    print(f"\n=== Step 4: Staging Assets ===")
    staged_audio_path = assets_dir / f"{args.sign.lower()}-audio.mp3"
    shutil.copy2(audio_output_path, staged_audio_path)
    
    staged_bg_path = assets_dir / "placeholder-bg.mp4"
    if not staged_bg_path.exists():
        print(f"[INFO] {staged_bg_path} does not exist; creating dummy placeholder video via ffmpeg...")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=0x1a0933:s=1080x1920:d=30",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", "30",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
            str(staged_bg_path)
        ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print(f"\n=== Step 5: Writing Remotion Props File ===")
    props = {
        "signName": args.sign,
        "captionText": caption_text,
        "backgroundVideoPath": "assets/placeholder-bg.mp4",
        "audioPath": f"assets/{args.sign.lower()}-audio.mp3",
        "durationInSeconds": duration_seconds,
    }
    args.props_out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.props_out, "w") as f:
        json.dump(props, f, indent=2)
        f.write("\n")
    print(f"Wrote props to {args.props_out}")

    if args.skip_render:
        print("\n[INFO] --skip-render set. Remotion rendering skipped.")
        print("Ready for rendering with: npx remotion render src/index.ts HoroscopeVideo out/video.mp4 --props=" + str(args.props_out.relative_to(remotion_dir) if args.props_out.is_relative_to(remotion_dir) else args.props_out))
        return

    print(f"\n=== Step 6: Rendering Remotion Video ===")
    out_video_path = remotion_dir / "out" / f"{args.sign.lower()}_test.mp4"
    out_video_path.parent.mkdir(parents=True, exist_ok=True)

    rel_props = os.path.relpath(args.props_out, remotion_dir)
    render_cmd = [
        "npx", "remotion", "render",
        "src/index.ts", "HoroscopeVideo",
        str(out_video_path),
        f"--props={rel_props}"
    ]
    print(f"Running: {' '.join(render_cmd)}")
    subprocess.run(render_cmd, cwd=remotion_dir, check=True)
    print(f"Render completed successfully! Output: {out_video_path}")


if __name__ == "__main__":
    main()
