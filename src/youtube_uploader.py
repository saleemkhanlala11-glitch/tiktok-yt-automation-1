import os
import re
import json
import logging
import time
from typing import List, Optional, Dict, Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

logger = logging.getLogger("youtube_uploader")

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

def clean_title(raw_title: str, max_length: int = 100) -> str:
    """Cleans TikTok caption to create an engaging YouTube Shorts title <= 100 chars."""
    if not raw_title:
        return "#Shorts"

    # Remove URL links if present
    cleaned = re.sub(r"https?://\S+", "", raw_title).strip()
    # Normalize whitespace
    cleaned = re.sub(r"\s+", " ", cleaned)

    if "#shorts" not in cleaned.lower() and len(cleaned) <= max_length - 8:
        cleaned = f"{cleaned} #shorts"

    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length - 3].rstrip() + "..."

    return cleaned

class YouTubeUploader:
    def __init__(self, token_file: str, client_secret_file: str):
        self.token_file = token_file
        self.client_secret_file = client_secret_file
        self.creds: Optional[Credentials] = None
        self._authenticate()

    def _authenticate(self):
        if not os.path.exists(self.token_file):
            raise FileNotFoundError(f"OAuth token file not found at {self.token_file}")

        with open(self.token_file, "r", encoding="utf-8") as f:
            token_data = json.load(f)

        self.creds = Credentials.from_authorized_user_info(token_data, scopes=SCOPES)

        if not self.creds.valid:
            if self.creds.expired and self.creds.refresh_token:
                logger.info("Refreshing expired YouTube OAuth credentials...")
                self.creds.refresh(Request())
                with open(self.token_file, "w", encoding="utf-8") as f:
                    f.write(self.creds.to_json())
                logger.info("Credentials refreshed and saved successfully.")
            else:
                raise ValueError("Credentials invalid and no refresh token available.")

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        category_id: str = "22",
        tags: Optional[List[str]] = None,
        is_short: bool = True,
        dry_run: bool = False
    ) -> str:
        """
        Uploads a video to YouTube as public.
        If dry_run is True, logs intent and returns mock video ID.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")

        final_title = clean_title(title, max_length=100)
        final_tags = list(tags) if tags else []
        if is_short and "Shorts" not in final_tags and "shorts" not in final_tags:
            final_tags.append("Shorts")

        body = {
            "snippet": {
                "title": final_title,
                "description": description.strip(),
                "tags": final_tags,
                "categoryId": str(category_id)
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        if dry_run:
            logger.info("[DRY RUN] Would upload to YouTube with:")
            logger.info(f"  Title: {final_title}")
            logger.info(f"  Tags: {final_tags}")
            logger.info(f"  Category: {category_id}")
            logger.info(f"  File size: {os.path.getsize(file_path)} bytes")
            return f"dry_run_{int(time.time())}"

        self._authenticate()
        youtube = build("youtube", "v3", credentials=self.creds)

        media = MediaFileUpload(
            file_path,
            mimetype="video/mp4",
            resumable=True,
            chunksize=1024 * 1024 * 4  # 4MB chunks
        )

        request = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        logger.info(f"Initiating YouTube upload for '{final_title}'...")
        response = None
        retry_delay = 5
        while response is None:
            try:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload progress: {progress}%")
            except HttpError as e:
                if e.resp.status in [500, 502, 503, 504]:
                    logger.warning(f"Temporary server error ({e.resp.status}). Retrying in {retry_delay}s...")
                    time.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 60)
                else:
                    content = e.content.decode("utf-8", errors="replace")
                    if "authenticatedUserAccountSuspended" in content:
                        logger.critical("FATAL: YouTube channel was terminated (authenticatedUserAccountSuspended).")
                    raise

        video_id = response.get("id")
        logger.info(f"Upload successful! YouTube Video ID: {video_id} (https://youtu.be/{video_id})")
        return video_id
