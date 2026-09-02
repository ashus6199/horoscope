#!/usr/bin/env python3
"""
Publish a rendered video to Instagram Reels via Meta Graph API.

Requirements:
  - An Instagram Business or Creator Account linked to a Facebook Page.
  - A Meta Graph API Access Token with `instagram_basic` and `instagram_content_publish` permissions.
  - A publicly accessible HTTPS URL for the video file.

Environment Variables Expected (if CLI flags omitted):
  - INSTAGRAM_USER_ID: Meta Instagram Account ID
  - INSTAGRAM_ACCESS_TOKEN: Long-lived Meta Graph API Access Token

Usage:
  python publish_instagram.py --video-url "https://..." --caption "Daily horoscope ✨ #horoscope #sagittarius"
  python publish_instagram.py --dry-run
"""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
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


def create_reels_container(ig_user_id: str, access_token: str, video_url: str, caption: str) -> str:
    """Step 1: Create a Reels media container."""
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
    return container_id


def poll_container_status(container_id: str, access_token: str, max_attempts: int = 30, delay_seconds: int = 5) -> None:
    """Step 2: Poll container status until status_code == FINISHED."""
    endpoint = f"{GRAPH_BASE_URL}/{container_id}?fields=status_code,status&access_token={access_token}"

    for attempt in range(1, max_attempts + 1):
        res = make_request(endpoint, method="GET")
        status_code = res.get("status_code")
        status_desc = res.get("status", "")

        if status_code == "FINISHED":
            return
        elif status_code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Media container processing failed ({status_code}): {status_desc}")

        time.sleep(delay_seconds)

    raise TimeoutError(f"Container processing timed out after {max_attempts * delay_seconds} seconds.")


def publish_container(ig_user_id: str, access_token: str, container_id: str) -> Dict[str, Any]:
    """Step 3: Publish the FINISHED media container."""
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


def publish_reel(ig_user_id: str, access_token: str, video_url: str, caption: str) -> Dict[str, Any]:
    """Executes full 3-step Reels publishing flow."""
    container_id = create_reels_container(ig_user_id, access_token, video_url, caption)
    poll_container_status(container_id, access_token)
    result = publish_container(ig_user_id, access_token, container_id)
    return result


def main():
    parser = argparse.ArgumentParser(description="Publish Instagram Reel via Meta Graph API")
    parser.add_argument("--video-url", help="Public HTTPS URL of rendered video file")
    parser.add_argument("--caption", default="Daily horoscope ✨\n\n#horoscope #sagittarius", help="Reel caption text")
    parser.add_argument("--ig-user-id", default=os.environ.get("INSTAGRAM_USER_ID"), help="Instagram Business Account ID")
    parser.add_argument("--access-token", default=os.environ.get("INSTAGRAM_ACCESS_TOKEN"), help="Meta Graph API Access Token")
    parser.add_argument("--jitter-max-seconds", type=int, default=0, help="Random delay in seconds before publishing (anti-bot protection)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate publishing without calling Meta Graph API")
    args = parser.parse_args()

    if args.dry_run:
        mock_result = {
            "status": "dry_run",
            "video_url": args.video_url or "https://example.com/horoscope.mp4",
            "caption": args.caption,
            "media_id": "dry_run_media_12345",
            "message": "Dry-run mode enabled; skipped Meta Graph API call."
        }
        print(json.dumps(mock_result, indent=2))
        return

    if not args.video_url:
        print("ERROR: --video-url is required when not running in --dry-run mode.", file=sys.stderr)
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
        pub_result = publish_reel(args.ig_user_id, args.access_token, args.video_url, args.caption)
        pub_result["status"] = "success"
        print(json.dumps(pub_result, indent=2))
    except Exception as e:
        err_res = {"status": "error", "error": str(e)}
        print(json.dumps(err_res, indent=2), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
