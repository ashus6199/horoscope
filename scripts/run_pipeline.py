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
    parser.add_argument("--publish-ig", action="store_true", help="Publish rendered video to Instagram Reels")
    parser.add_argument("--video-url", help="Public video HTTPS URL for Instagram publishing (required if --publish-ig)")
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
    
    beat_keys = ["hook", "context", "sharp_line", "compatibility_line"]
    spoken_parts = []
    for k in beat_keys:
        val = horoscope_data.get(f"spoken_{k}") or horoscope_data.get(k) or ""
        if val:
            spoken_parts.append(val)

    spoken_text = " ".join(spoken_parts)
    post_caption = horoscope_data.get("caption", spoken_text)
    print(f"Spoken Script ({horoscope_data.get('word_count')} words):\n{spoken_text}")
    print(f"Post Caption: {post_caption}")

    print(f"\n=== Step 3: Generating TTS Audio ===")
    audio_filename = f"{args.sign.lower()}.mp3"
    audio_output_path = args.output_dir / audio_filename
    tts_cmd = [
        sys.executable, str(scripts_dir / "generate_tts.py"),
        "--text", spoken_text,
        "--output", str(audio_output_path),
    ]
    if args.dry_run:
        tts_cmd.append("--dry-run")
    tts_output_json = run_command(tts_cmd, cwd=repo_root)
    tts_data = json.loads(tts_output_json)
    duration_seconds = tts_data["duration_seconds"]
    word_timings = tts_data.get("word_timings", [])
    print(f"Generated TTS audio: {audio_output_path} (Duration: {duration_seconds}s)")
    print(f"Captured {len(word_timings)} word timings for caption sync")

    import re
    card_blocks = []
    w_idx = 0
    prev_end = 0.0
    for key in beat_keys:
        card_text = horoscope_data.get(f"card_{key}") or horoscope_data.get(key) or ""
        spoken_val = horoscope_data.get(f"spoken_{key}") or horoscope_data.get(key) or ""
        if not card_text:
            continue

        spoken_words = re.sub(r'[—–-]+', ' ', spoken_val).split()
        count = len(spoken_words)
        block_words = word_timings[w_idx : min(w_idx + count, len(word_timings))]
        w_idx += count

        start = block_words[0]["start"] if block_words else prev_end
        end = block_words[-1]["end"] if block_words else start + 2.0
        prev_end = end

        card_blocks.append({
            "key": key,
            "text": card_text,
            "spokenText": spoken_val,
            "start": start,
            "end": end,
            "isSharpLine": (key == "sharp_line"),
            "words": block_words,
        })

    print(f"\n=== Step 4: Staging Assets ===")
    staged_audio_path = assets_dir / f"{args.sign.lower()}-audio.mp3"
    shutil.copy2(audio_output_path, staged_audio_path)
    
    chosen_clip_filename = clip_data.get("filename")
    if not chosen_clip_filename:
        raise ValueError("Selected clip entry has no 'filename' field")

    chosen_clip_path = assets_dir / chosen_clip_filename
    if not chosen_clip_path.exists():
        print(f"[ERROR] Selected clip file '{chosen_clip_filename}' not found at {chosen_clip_path}", file=sys.stderr)
        print(f"[ERROR] Place the file into remotion/public/assets/ before running the pipeline.", file=sys.stderr)
        raise RuntimeError(f"Missing background clip asset: {chosen_clip_path}")

    # Create a perfectly seamless crossfade loop using ffmpeg
    loop_filename = f"loop_{chosen_clip_filename}"
    loop_path = assets_dir / loop_filename
    
    if not loop_path.exists():
        print(f"Generating seamless crossfade loop for {chosen_clip_filename}...")
        
        # 1. Get original duration
        dur_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(chosen_clip_path)
        ]
        orig_dur = float(subprocess.run(dur_cmd, capture_output=True, text=True, check=True).stdout.strip())
        
        # 2. Calculate split and crossfade points
        mid = orig_dur / 2.0
        xfade = 1.0 if orig_dur >= 3.0 else (orig_dur / 3.0)
        offset = mid - xfade
        
        # 2.5 Check if video has audio stream
        has_audio_cmd = [
            "ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
            "stream=codec_type", "-of", "csv=p=0", str(chosen_clip_path)
        ]
        has_audio = bool(subprocess.run(has_audio_cmd, capture_output=True, text=True, check=True).stdout.strip())

        # 3. ffmpeg split and crossfade
        if has_audio:
            filter_complex = (
                f"[0:v]trim=start={mid}:end={orig_dur},setpts=PTS-STARTPTS[part2];"
                f"[0:v]trim=start=0:end={mid},setpts=PTS-STARTPTS[part1];"
                f"[part2][part1]xfade=transition=fade:duration={xfade}:offset={offset}[outv];"
                f"[0:a]atrim=start={mid}:end={orig_dur},asetpts=PTS-STARTPTS[apart2];"
                f"[0:a]atrim=start=0:end={mid},asetpts=PTS-STARTPTS[apart1];"
                f"[apart2][apart1]acrossfade=d={xfade}[outa]"
            )
            maps = ["-map", "[outv]", "-map", "[outa]", "-c:a", "aac"]
        else:
            filter_complex = (
                f"[0:v]trim=start={mid}:end={orig_dur},setpts=PTS-STARTPTS[part2];"
                f"[0:v]trim=start=0:end={mid},setpts=PTS-STARTPTS[part1];"
                f"[part2][part1]xfade=transition=fade:duration={xfade}:offset={offset}[outv]"
            )
            maps = ["-map", "[outv]"]

        cmd = [
            "ffmpeg", "-y", "-i", str(chosen_clip_path),
            "-filter_complex", filter_complex,
        ] + maps + [
            "-c:v", "libx264", "-preset", "ultrafast",
            str(loop_path)
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"Created {loop_filename}")

    # Extract exact duration of the seamless loop clip
    duration_cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(loop_path)
    ]
    duration_output = subprocess.run(duration_cmd, capture_output=True, text=True, check=True).stdout.strip()
    bg_duration_seconds = float(duration_output)

    bg_video_path = f"assets/{loop_filename}"
    print(f"Using background clip: {bg_video_path} (Duration: {bg_duration_seconds}s)")

    from datetime import datetime
    date_text = datetime.now().strftime("%d %B %Y")

    print(f"\n=== Step 5: Writing Remotion Props File ===")
    props = {
        "signName": args.sign,
        "captionText": post_caption,
        "spokenText": spoken_text,
        "cardBlocks": card_blocks,
        "backgroundVideoPath": bg_video_path,
        "audioPath": f"assets/{args.sign.lower()}-audio.mp3",
        "durationInSeconds": duration_seconds,
        "bgDurationSeconds": bg_duration_seconds,
        "dateText": date_text,
        "wordTimings": word_timings,
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

    ffmpeg_bin = shutil.which("ffmpeg")
    ffprobe_bin = shutil.which("ffprobe")
    if ffmpeg_bin and ffprobe_bin:
        render_cmd.extend([
            f"--ffmpeg-executable={ffmpeg_bin}",
            f"--ffprobe-executable={ffprobe_bin}"
        ])

    print(f"Running: {' '.join(render_cmd)}")
    subprocess.run(render_cmd, cwd=remotion_dir, check=True)
    # NOTE: Unreachable when --skip-render is passed in CI; kept for standalone local CLI runs.
    # Re-mux with -movflags +faststart to ensure moov atom is at the front of the MP4 container for Meta API Reels spec
    faststart_path = out_video_path.parent / f"{args.sign.lower()}_faststart.mp4"
    faststart_cmd = [
        ffmpeg_bin or "ffmpeg", "-y",
        "-i", str(out_video_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(faststart_path)
    ]
    print(f"Re-muxing for faststart: {' '.join(faststart_cmd)}")
    subprocess.run(faststart_cmd, check=True)
    print(f"Faststart video ready: {faststart_path}")

    if args.publish_ig:
        print(f"\n=== Step 7: Publishing to Instagram Reels ===")
        ig_caption = post_caption
        
        pub_cmd = [
            sys.executable, str(scripts_dir / "publish_instagram.py"),
            "--caption", ig_caption,
            "--video-path", str(faststart_path),
        ]
        if not args.dry_run:
            pub_cmd.extend(["--jitter-max-seconds", "300"])
        if args.video_url:
            pub_cmd.extend(["--video-url", args.video_url])
        if args.dry_run:
            pub_cmd.append("--dry-run")

        print(f"Executing: {' '.join(pub_cmd)}")
        pub_out = run_command(pub_cmd, cwd=repo_root)
        print(f"Publishing Output:\n{pub_out}")


if __name__ == "__main__":
    main()