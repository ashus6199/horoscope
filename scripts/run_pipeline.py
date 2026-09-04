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
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        if e.stdout:
            print(f"[SUBPROCESS ERROR STDOUT]\n{e.stdout.strip()}", file=sys.stderr)
        if e.stderr:
            print(f"[SUBPROCESS ERROR STDERR]\n{e.stderr.strip()}", file=sys.stderr)
        raise


SIGN_ELEMENT_MAP = {
    "aries": "fire", "leo": "fire", "sagittarius": "fire",
    "taurus": "earth", "virgo": "earth", "capricorn": "earth",
    "gemini": "air", "libra": "air", "aquarius": "air",
    "cancer": "water", "scorpio": "water", "pisces": "water",
}


def main():
    parser = argparse.ArgumentParser(description="Run full Horoscope video pipeline")
    parser.add_argument("--sign", required=True, help="Zodiac sign (e.g. Sagittarius)")
    parser.add_argument("--element", choices=["fire", "earth", "air", "water"], help="Element (auto-derived from sign if omitted)")
    parser.add_argument("--manifest", type=Path, default=Path("manifest/manifest.json"))
    parser.add_argument("--mark-used", action="store_true", help="Mark selected clip as used in manifest (enabled by default for real runs)")
    parser.add_argument("--no-mark-used", action="store_true", help="Prevent marking selected clip as used in manifest")
    parser.add_argument("--dry-run", action="store_true", help="Use dry-run/mock responses")
    parser.add_argument("--skip-render", action="store_true", help="Prepare assets and props but skip Remotion render step")
    parser.add_argument("--date", help="Override date (YYYY-MM-DD) for testing historical or future events")
    parser.add_argument("--publish-ig", action="store_true", help="Publish rendered video to Instagram Reels")
    parser.add_argument("--video-url", help="Public video HTTPS URL for Instagram publishing (required if --publish-ig)")
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--props-out", type=Path, default=Path("remotion/props.json"))
    args = parser.parse_args()

    element = args.element or SIGN_ELEMENT_MAP.get(args.sign.lower(), "fire")
    args.element = element

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
    should_mark = (not args.no_mark_used and not args.dry_run) or args.mark_used
    if should_mark:
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
    if args.date:
        horoscope_cmd.extend(["--date", args.date])
    if args.dry_run or not os.environ.get("OPENAI_API_KEY"):
        print("[INFO] Using --dry-run for text generation (no OPENAI_API_KEY found or --dry-run passed)")
        horoscope_cmd.append("--dry-run")
    horoscope_output_json = run_command(horoscope_cmd, cwd=repo_root)
    horoscope_data = json.loads(horoscope_output_json)

    # Extract transit metadata from the horoscope JSON output
    transit_ctx = horoscope_data.get("transit_context", "")
    # Re-run get_transits.py to get structured transit data for Remotion props
    transit_meta = {
        "moonSign": "",
        "moonPhase": "",
        "moonPhasePct": 50.0,
        "moonAgeDays": 14.0,
        "bestSign": "",
        "cautionSign": "",
    }
    try:
        transit_cmd = [sys.executable, str(scripts_dir / "get_transits.py"), "--sign", args.sign]
        if args.date:
            transit_cmd.extend(["--date", args.date])
        transit_json = run_command(transit_cmd, cwd=repo_root)
        transit_data = json.loads(transit_json)
        transit_meta["moonSign"] = transit_data.get("moon_sign", "")
        transit_meta["moonPhase"] = transit_data.get("moon_phase_label", "")
        transit_meta["moonPhasePct"] = transit_data.get("moon_phase_pct", 50.0)
        transit_meta["moonAgeDays"] = transit_data.get("moon_age_days", 14.0)
        transit_meta["eventAlert"] = transit_data.get("event_alert", None)
        compat = transit_data.get("compatibility", {})
        transit_meta["bestSign"] = compat.get("harmonious_pick", "")
        transit_meta["cautionSign"] = compat.get("friction_pick", "")
    except Exception as e:
        print(f"[WARNING] Could not extract transit metadata ({e})", file=sys.stderr)

    # Build spoken script from 6 spoken beats
    spoken_beat_keys = [
        "spoken_hook", "spoken_sky_weather", "spoken_context",
        "spoken_sharp_line", "spoken_compatibility_line", "spoken_reflection"
    ]
    spoken_parts = [horoscope_data.get(k, "") for k in spoken_beat_keys]
    spoken_parts = [p for p in spoken_parts if p]

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
    def norm(w):
        return re.sub(r'[^a-z0-9]', '', w.lower())

    norm_timings = [norm(wt.get("word", "")) for wt in word_timings]

    # Map each spoken beat to exact word-boundary timestamps
    def find_beat_timing(spoken_text_val, w_cursor_start, prev_end_val):
        spoken_words = [norm(w) for w in re.sub(r'[—–-]+', ' ', spoken_text_val).split() if norm(w)]
        count = len(spoken_words)
        start_idx = w_cursor_start
        if spoken_words:
            first_word = spoken_words[0]
            for search_i in range(w_cursor_start, min(w_cursor_start + 15, len(norm_timings))):
                if norm_timings[search_i] == first_word:
                    start_idx = search_i
                    break
        end_idx = min(start_idx + count, len(word_timings))
        block_words = word_timings[start_idx : end_idx]
        new_cursor = max(end_idx, start_idx + 1)
        start = block_words[0]["start"] if block_words else prev_end_val
        end = block_words[-1]["end"] if block_words else start + 2.0
        return start, end, block_words, new_cursor

    w_cursor = 0
    prev_end = 0.0
    card_blocks = []

    # --- Card 1: Hook (moon transit) ---
    spoken_hook = horoscope_data.get("spoken_hook", "")
    if spoken_hook:
        start, end, bw, w_cursor = find_beat_timing(spoken_hook, w_cursor, prev_end)
        prev_end = end
        card_blocks.append({
            "key": "hook",
            "text": horoscope_data.get("card_hook", ""),
            "spokenText": spoken_hook,
            "start": start, "end": end,
            "isSharpLine": False,
            "words": bw,
        })

    # --- Card 2: Sky Weather & Retrogrades ---
    spoken_sky_weather = horoscope_data.get("spoken_sky_weather", "")
    if spoken_sky_weather:
        start, end, bw, w_cursor = find_beat_timing(spoken_sky_weather, w_cursor, prev_end)
        prev_end = end
        card_blocks.append({
            "key": "sky_weather",
            "text": horoscope_data.get("card_sky_weather", ""),
            "skyWeatherText": horoscope_data.get("card_sky_weather", ""),
            "spokenText": spoken_sky_weather,
            "start": start, "end": end,
            "isSharpLine": False,
            "words": bw,
        })

    # --- Card 3: Context (power focus + color) ---
    spoken_context = horoscope_data.get("spoken_context", "")
    if spoken_context:
        start, end, bw, w_cursor = find_beat_timing(spoken_context, w_cursor, prev_end)
        prev_end = end
        card_blocks.append({
            "key": "context",
            "text": horoscope_data.get("power_focus", ""),
            "powerFocus": horoscope_data.get("power_focus", ""),
            "powerColor": horoscope_data.get("power_color", ""),
            "spokenText": spoken_context,
            "start": start, "end": end,
            "isSharpLine": False,
            "words": bw,
        })

    # --- Card 4: Sharp Line (DO / DON'T) ---
    spoken_sharp = horoscope_data.get("spoken_sharp_line", "")
    if spoken_sharp:
        start, end, bw, w_cursor = find_beat_timing(spoken_sharp, w_cursor, prev_end)
        prev_end = end
        card_blocks.append({
            "key": "sharp_line",
            "text": horoscope_data.get("sharp_do", ""),
            "sharpDo": horoscope_data.get("sharp_do", ""),
            "sharpDont": horoscope_data.get("sharp_dont", ""),
            "spokenText": spoken_sharp,
            "start": start, "end": end,
            "isSharpLine": True,
            "words": bw,
        })

    # --- Card 5: Compatibility (Best Energy & Handle With Care) ---
    spoken_compat = horoscope_data.get("spoken_compatibility_line", "")
    if spoken_compat:
        start, end, bw, w_cursor = find_beat_timing(spoken_compat, w_cursor, prev_end)
        prev_end = end
        card_blocks.append({
            "key": "compatibility_line",
            "text": transit_meta["bestSign"],
            "bestSign": transit_meta["bestSign"],
            "cautionSign": transit_meta["cautionSign"],
            "spokenText": spoken_compat,
            "start": start, "end": end,
            "isSharpLine": False,
            "words": bw,
        })

    # --- Card 6: Dedicated Journal Reflection ---
    spoken_reflection = horoscope_data.get("spoken_reflection", "")
    if spoken_reflection:
        start, end, bw, w_cursor = find_beat_timing(spoken_reflection, w_cursor, prev_end)
        prev_end = end
        card_blocks.append({
            "key": "reflection",
            "text": horoscope_data.get("reflection_question", ""),
            "reflectionQuestion": horoscope_data.get("reflection_question", ""),
            "spokenText": spoken_reflection,
            "start": start, "end": end,
            "isSharpLine": False,
            "words": bw,
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
    if args.date:
        date_text = datetime.strptime(args.date, "%Y-%m-%d").strftime("%d %B %Y")
    else:
        date_text = datetime.now().strftime("%d %B %Y")

    print(f"\n=== Step 5: Writing Remotion Props File ===")
    props = {
        "signName": args.sign,
        "captionText": post_caption,
        "spokenText": spoken_text,
        "moonSign": transit_meta["moonSign"],
        "moonPhase": transit_meta["moonPhase"],
        "moonPhasePct": transit_meta["moonPhasePct"],
        "moonAgeDays": transit_meta["moonAgeDays"],
        "bestSign": transit_meta["bestSign"],
        "cautionSign": transit_meta["cautionSign"],
        "eventAlert": transit_meta.get("eventAlert"),
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