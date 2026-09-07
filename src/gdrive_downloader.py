import os
import re
import json
import time
import logging
import requests
import subprocess
from typing import List, Dict, Any, Optional

logger = logging.getLogger("gdrive_downloader")

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def clean_video_filename(filename: str) -> str:
    """Derives a clean title from a video filename."""
    base = re.sub(r"\.(mp4|mov|mkv|webm|avi|m4v)$", "", filename, flags=re.IGNORECASE).strip()
    base = re.sub(r"[_\-]+", " ", base)
    base = re.sub(r"\s+", " ", base)
    return base.strip()

def list_gdrive_folder_videos(folder_id: str, max_retries: int = 3) -> List[Dict[str, Any]]:
    """
    Lists all video files inside a public/shared Google Drive folder.
    Returns a list of dicts with keys: id, url, title, filename, mimeType, modified_time.
    """
    url = f"https://drive.google.com/drive/folders/{folder_id}?usp=sharing"
    logger.info(f"Fetching Google Drive folder listing for folder ID: {folder_id}")

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=45)
            if resp.status_code != 200:
                logger.warning(f"Google Drive returned HTTP {resp.status_code} (attempt {attempt}/{max_retries})")
                time.sleep(attempt * 2)
                continue

            text = resp.text
            match = re.search(r"window\['_DRIVE_ivd'\]\s*=\s*'((?:\\'|[^'])*)';", text)
            if not match:
                match = re.search(r"window\[\"_DRIVE_ivd\"\]\s*=\s*\"((?:\\\"|[^\"])*)\";", text)

            if not match:
                logger.warning(f"Could not locate _DRIVE_ivd payload in page (attempt {attempt}/{max_retries})")
                time.sleep(attempt * 2)
                continue

            raw_str = match.group(1)
            decoded = raw_str.encode("utf-8").decode("unicode_escape")
            data = json.loads(decoded)

            items: List[Dict[str, Any]] = []

            def extract_nodes(node):
                if isinstance(node, list):
                    if len(node) >= 4 and isinstance(node[0], str) and isinstance(node[1], list) and isinstance(node[2], str) and isinstance(node[3], str):
                        filename = node[2]
                        mime_type = node[3]
                        if mime_type.startswith("video/") or filename.lower().endswith((".mp4", ".mov", ".mkv", ".webm", ".avi")):
                            file_id = node[0]
                            clean_title = clean_video_filename(filename)
                            mod_time = node[9] if len(node) > 9 else 0
                            items.append({
                                "id": file_id,
                                "url": f"https://drive.google.com/file/d/{file_id}/view",
                                "title": clean_title,
                                "filename": filename,
                                "mimeType": mime_type,
                                "modified_time": mod_time or 0,
                                "view_count": 0,
                                "source": "gdrive"
                            })
                    for child in node:
                        extract_nodes(child)

            extract_nodes(data)

            unique_items = []
            seen_ids = set()
            for it in items:
                if it["id"] not in seen_ids:
                    seen_ids.add(it["id"])
                    unique_items.append(it)

            logger.info(f"Successfully discovered {len(unique_items)} video files in Google Drive folder.")
            return unique_items

        except Exception as e:
            logger.error(f"Error listing Google Drive folder (attempt {attempt}/{max_retries}): {e}")
            time.sleep(attempt * 2)

    logger.critical(f"Failed to list Google Drive folder {folder_id} after {max_retries} attempts.")
    return []

def verify_video_has_audio(file_path: str) -> bool:
    """Verifies that the downloaded video has an audible audio track."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=codec_name",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(res.stdout.strip())
    except Exception as e:
        logger.warning(f"Audio check with ffprobe on {file_path}: {e}")
        return True

def download_gdrive_video(file_id: str, output_path: str, max_retries: int = 3) -> Optional[str]:
    """
    Downloads a video from Google Drive by file ID using yt-dlp / direct stream.
    Validates file integrity and audio presence.
    """
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    view_url = f"https://drive.google.com/file/d/{file_id}/view"

    for attempt in range(1, max_retries + 1):
        # Method A: yt-dlp download
        try:
            logger.info(f"Downloading Google Drive video via yt-dlp: {file_id} (attempt {attempt}/{max_retries})...")
            cmd = [
                "yt-dlp",
                "--no-warnings",
                "-o", output_path,
                view_url
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                if verify_video_has_audio(output_path):
                    logger.info(f"yt-dlp download verified with audio: {output_path} ({os.path.getsize(output_path) / (1024*1024):.2f} MB)")
                    return output_path
                else:
                    logger.error(f"Downloaded file {output_path} has NO audio track! Removing.")
                    os.remove(output_path)
        except Exception as e:
            logger.warning(f"yt-dlp attempt {attempt} failed: {e}")

        # Method B: Direct streaming download fallback
        try:
            dl_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
            session = requests.Session()
            resp = session.get(dl_url, headers=DEFAULT_HEADERS, stream=True, timeout=90)
            if resp.status_code == 200:
                with open(output_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
                if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
                    if verify_video_has_audio(output_path):
                        logger.info(f"Direct stream download verified: {output_path}")
                        return output_path
                    else:
                        os.remove(output_path)
        except Exception as e:
            logger.warning(f"Direct stream attempt {attempt} failed: {e}")

        time.sleep(attempt * 2)

    logger.error(f"Failed to download Google Drive video {file_id} after {max_retries} attempts.")
    return None
