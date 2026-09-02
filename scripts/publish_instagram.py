#!/usr/bin/env python3
"""
Publish a rendered video to Instagram Reels via Meta Graph API.

Supports two video upload mechanisms:
  1. Direct Binary Resumable Upload (--video-path): Uploads video file bytes directly
     to Meta's upload servers (rupload.facebook.com). 100% reliable, zero external URL dependencies.
  2. External URL Upload (--video-url): Meta fetches the video from a public HTTPS URL.

Environment Variables Expected:
  - INSTAGRAM_USER_ID: Meta Instagram Account ID
  - INSTAGRAM_ACCESS_TOKEN: Long-lived Meta Graph API Access Token

Usage:
  python publish_instagram.py --video-path remotion/out/sagittarius_test.mp4 --caption "Daily horoscope ✨ #horoscope #sagittarius"
  python publish_instagram.py --dry-run
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Dict, Any

GRAPH_API_VERSION = "v20.0"
GRAPH_BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"


def make_request(url: str, method: str = "GET", data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Helper function to make HTTP requests to the Meta Graph API."""
    req_data = None
    if data:
        req_data = urllib.parse.urlencode(data).encode("utf-8")

    req = urllib.request.Request(url, data=req_data, method=method)
    req.add_header("Content-Type", "application/x-www-form-urlencoded")

    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return json.loads(res_body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_body)
            error_msg = err_json.get("error", {}).get("message", err_body)
        except Exception:
            error_msg = err_body
        raise RuntimeError(f"Meta Graph API error (HTTP {e.code}): {error_msg}")


def poll_container_status(container_id: str, access_token: str, max_attempts: int = 36, delay_seconds: int = 5) -> None:
    """Poll container status until status_code == FINISHED."""
    endpoint = f"{GRAPH_BASE_URL}/{container_id}?fields=status_code,status&access_token={access_token}"

    for attempt in range(1, max_attempts + 1):
        res = make_request(endpoint, method="GET")
        status_code = res.get("status_code")
        status_desc = res.get("status", "")

        if status_code == "FINISHED":
            print(f"[INFO] Container {container_id} processing FINISHED cleanly.", file=sys.stderr)
            return
        elif status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Media container processing failed ({status_code}): {status_desc}")

        time.sleep(delay_seconds)

    raise TimeoutError(f"Container processing timed out after {max_attempts * delay_seconds} seconds.")


def publish_container(ig_user_id: str, access_token: str, container_id: str) -> Dict[str, Any]:
    """Publish the FINISHED media container to Instagram Reels."""
    endpoint = f"{GRAPH_BASE_URL}/{ig_user_id}/media_publish"
    payload = {
        "creation_id": container_id,
        "access_token": access_token,
    }
    res = make_request(endpoint, method="POST", data=payload)
    media_id = res.get("id")
    if not media_id:
        raise RuntimeError(f"Failed to publish container: {res}")
    return {"media_id": media_id}


def publish_reel_resumable(ig_user_id: str, access_token: str, video_path: Path, caption: str) -> Dict[str, Any]:
    """
    Bulletproof Direct Binary Resumable Upload Protocol (rupload.facebook.com).
    Streams video binary bytes directly to Meta's servers without any external host dependency.
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video file does not exist: {video_path}")

    file_size = video_path.stat().st_size
    print(f"[INFO] Initiating Direct Resumable Upload for {video_path.name} ({file_size} bytes)...", file=sys.stderr)

    # Step 1: Initialize Resumable Session
    init_endpoint = f"{GRAPH_BASE_URL}/{ig_user_id}/media"
    init_payload = {
        "media_type": "REELS",
        "upload_type": "resumable",
        "caption": caption,
        "access_token": access_token,
    }
    init_res = make_request(init_endpoint, method="POST", data=init_payload)
    container_id = init_res.get("id")
    upload_uri = init_res.get("uri", f"https://rupload.facebook.com/ig-api-upload/v20.0/{container_id}")

    if not container_id:
        raise RuntimeError(f"Failed to initialize resumable media container: {init_res}")

    print(f"[INFO] Container created ({container_id}). Uploading binary payload to Meta rupload endpoint...", file=sys.stderr)

    # Step 2: Stream Video Binary Bytes to rupload.facebook.com
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    req = urllib.request.Request(upload_uri, data=video_bytes, method="POST")
    req.add_header("Authorization", f"OAuth {access_token}")
    req.add_header("offset", "0")
    req.add_header("file_size", str(file_size))
    req.add_header("Content-Type", "application/octet-stream")

    try:
        with urllib.request.urlopen(req) as resp:
            upload_res = json.loads(resp.read().decode("utf-8"))
            print(f"[INFO] Direct binary upload response: {upload_res}", file=sys.stderr)
            if not upload_res.get("success", True) and upload_res.get("success") is not None:
                raise RuntimeError(f"Meta rejected the upload payload: {upload_res}")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        raise RuntimeError(f"Meta rupload direct binary upload failed (HTTP {e.code}): {err_body}")

    # Step 3: Poll Container Processing Status
    print(f"[INFO] Polling Meta container ({container_id}) status...", file=sys.stderr)
    time.sleep(5)
    poll_container_status(container_id, access_token)

    # Step 4: Publish Reel
    print(f"[INFO] Publishing Reel container ({container_id}) live...", file=sys.stderr)
    result = publish_container(ig_user_id, access_token, container_id)
    return result


def publish_reel_url(ig_user_id: str, access_token: str, video_url: str, caption: str) -> Dict[str, Any]:
    """Fallback flow for public HTTPS URLs."""
    endpoint = f"{GRAPH_BASE_URL}/{ig_user_id}/media"
    payload = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": access_token,
    }
    res = make_request(endpoint, method="POST", data=payload)
    container_id = res.get("id")
    if not container_id:
        raise RuntimeError(f"Failed to create media container: {res}")

    print(f"[INFO] Container created ({container_id}). Waiting for video ingestion...", file=sys.stderr)
    time.sleep(8)
    poll_container_status(container_id, access_token)
    result = publish_container(ig_user_id, access_token, container_id)
    return result


def main():
    parser = argparse.ArgumentParser(description="Publish Instagram Reel via Meta Graph API Direct Resumable Upload")
    parser.add_argument("--video-path", type=Path, help="Local file path of rendered video file")
    parser.add_argument("--video-url", help="Public HTTPS URL of rendered video file (alternative to --video-path)")
    parser.add_argument("--caption", default="Daily horoscope ✨\n\n#horoscope #sagittarius", help="Reel caption text")
    parser.add_argument("--ig-user-id", default=os.environ.get("INSTAGRAM_USER_ID"), help="Instagram Business Account ID")
    parser.add_argument("--access-token", default=os.environ.get("INSTAGRAM_ACCESS_TOKEN"), help="Meta Graph API Access Token")
    parser.add_argument("--jitter-max-seconds", type=int, default=0, help="Random delay in seconds before publishing (anti-bot protection)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate publishing without calling Meta Graph API")
    args = parser.parse_args()

    if args.dry_run:
        mock_result = {
            "status": "dry_run",
            "video": str(args.video_path or args.video_url or "remotion/out/sagittarius_test.mp4"),
            "caption": args.caption,
            "media_id": "dry_run_media_12345",
            "message": "Dry-run mode enabled; skipped Meta Graph API call."
        }
        print(json.dumps(mock_result, indent=2))
        return

    if not args.video_path and not args.video_url:
        print("ERROR: Either --video-path or --video-url must be provided.", file=sys.stderr)
        sys.exit(1)

    if not args.ig_user_id or not args.access_token:
        print("ERROR: INSTAGRAM_USER_ID and INSTAGRAM_ACCESS_TOKEN must be set or passed via flags.", file=sys.stderr)
        sys.exit(1)

    if args.jitter_max_seconds > 0:
        import random
        sleep_sec = random.randint(1, args.jitter_max_seconds)
        print(f"[INFO] Anti-bot jitter protection: sleeping {sleep_sec}s before calling Meta API...", file=sys.stderr)
        time.sleep(sleep_sec)

    try:
        if args.video_path and args.video_path.exists():
            pub_result = publish_reel_resumable(args.ig_user_id, args.access_token, args.video_path, args.caption)
        else:
            pub_result = publish_reel_url(args.ig_user_id, args.access_token, args.video_url, args.caption)

        pub_result["status"] = "success"
        print(json.dumps(pub_result, indent=2))
    except Exception as e:
        err_res = {"status": "error", "error": str(e)}
        print(json.dumps(err_res, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
