import os
import json
import time
import subprocess
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("tiktok_downloader")

FORMAT_SELECTOR = (
    "bestvideo[format_id^=play][ext=mp4]+bestaudio"
    "/best[format_id^=play][ext=mp4][vcodec!=none]"
    "/best[format_id^=play][vcodec!=none]"
    "/best[format_id^=h264][ext=mp4][vcodec!=none]"
    "/best[ext=mp4][vcodec!=none]"
    "/best[vcodec!=none]"
)

FALLBACK_AUDIO_SAFE_SELECTOR = "best[vcodec!=none][acodec!=none]/best"

def get_cookie_file() -> Optional[str]:
    cookie_env = os.environ.get("TIKTOK_COOKIES_FILE")
    if cookie_env and os.path.exists(cookie_env):
        return cookie_env
    default_cookie = "cookies.txt"
    if os.path.exists(default_cookie):
        return default_cookie
    return None

def verify_has_audio(file_path: str) -> bool:
    """Uses ffprobe to verify that the downloaded video has an active audio stream."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "csv=p=0",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return "audio" in res.stdout.strip().lower()
    except Exception as e:
        logger.warning(f"ffprobe check failed for {file_path}: {e}")
        return False

def list_profile_videos(username: str, batch_size: int = 150, max_retries: int = 3) -> List[Dict[str, Any]]:
    """
    Lists TikTok profile videos using yt-dlp.
    Applies batch size = 150, Referer header, retries on empty response.
    Filters out photo/slideshow posts.
    """
    profile_url = f"https://www.tiktok.com/@{username.lstrip('@')}"
    cookie_file = get_cookie_file()

    for attempt in range(1, max_retries + 1):
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--dump-json",
            "--playlist-end", str(batch_size),
            "--add-header", "Referer: https://www.tiktok.com/",
            "--ignore-errors",
            "--no-warnings"
        ]
        if cookie_file:
            cmd.extend(["--cookies", cookie_file])
        cmd.append(profile_url)

        logger.info(f"Listing profile @{username} (attempt {attempt}/{max_retries})...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
            lines = [line.strip() for line in res.stdout.split("\n") if line.strip()]

            items = []
            for line in lines:
                try:
                    data = json.loads(line)
                    url = data.get("url", "")
                    if "/photo/" in url:
                        continue  # Skip slideshow / photo posts
                    items.append({
                        "id": str(data.get("id")),
                        "url": url or f"https://www.tiktok.com/@{username}/video/{data.get('id')}",
                        "title": data.get("title", ""),
                        "duration": data.get("duration"),
                        "view_count": data.get("view_count") or 0,
                        "upload_date": data.get("upload_date")
                    })
                except json.JSONDecodeError:
                    continue

            if items:
                logger.info(f"Successfully retrieved {len(items)} videos from @{username}")
                return items

            logger.warning(f"Empty listing returned for @{username} on attempt {attempt}")
        except Exception as e:
            logger.error(f"Error listing profile @{username}: {e}")

        if attempt < max_retries:
            backoff = 2 ** attempt
            time.sleep(backoff)

    logger.warning(f"No videos found for @{username} after {max_retries} attempts")
    return []

def download_tiktok_video(video_url: str, output_path: str, max_retries: int = 3) -> Optional[str]:
    """
    Downloads a TikTok video without watermark using yt-dlp.
    Verifies audio stream using ffprobe. Retries up to 3 times with pauses (4s, 8s).
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    cookie_file = get_cookie_file()

    def run_download(format_str: str) -> bool:
        cmd = [
            "yt-dlp",
            "-f", format_str,
            "-o", output_path,
            "--add-header", "Referer: https://www.tiktok.com/",
            "--no-warnings",
            "--force-overwrites"
        ]
        if cookie_file:
            cmd.extend(["--cookies", cookie_file])
        cmd.append(video_url)

        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        return res.returncode == 0 and os.path.exists(output_path)

    for attempt in range(1, max_retries + 1):
        logger.info(f"Downloading {video_url} (attempt {attempt}/{max_retries})...")
        success = run_download(FORMAT_SELECTOR)

        if success and verify_has_audio(output_path):
            logger.info(f"Download verified with audio: {output_path}")
            return output_path

        if success and not verify_has_audio(output_path):
            logger.warning(f"Downloaded video has no audio stream! Trying fallback audio-safe selector...")
            if os.path.exists(output_path):
                os.remove(output_path)
            fallback_success = run_download(FALLBACK_AUDIO_SAFE_SELECTOR)
            if fallback_success and verify_has_audio(output_path):
                logger.info(f"Fallback download succeeded with audio: {output_path}")
                return output_path
            else:
                logger.error("Video still lacks audio stream. Refusing silent video.")
                if os.path.exists(output_path):
                    os.remove(output_path)

        if attempt < max_retries:
            pause = 4 * attempt
            logger.info(f"Retrying download in {pause} seconds...")
            time.sleep(pause)

    logger.error(f"Failed to download valid video with audio for {video_url}")
    return None
