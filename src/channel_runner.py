import os
import shutil
import logging
from typing import Optional, List, Dict, Any

from .config import ChannelConfig
from .db import Database
from .tiktok_downloader import list_profile_videos, download_tiktok_video
from .video_converter import edit_short_video, get_video_duration
from .youtube_uploader import YouTubeUploader
from .notifier import send_discord_notification

logger = logging.getLogger("channel_runner")

def pick_candidate(
    items: List[Dict[str, Any]],
    slot: int,
    mode: str,
    posted_ids: set
) -> List[Dict[str, Any]]:
    unposted = [v for v in items if v["id"] not in posted_ids]
    if not unposted:
        return []

    if mode == "popular_split":
        if slot == 1:
            # Newest first (yt-dlp profile order is chronological newest-first)
            return unposted
        else:
            # Slot 2: most viewed first
            return sorted(unposted, key=lambda x: x.get("view_count", 0), reverse=True)
    elif mode == "short_only":
        return unposted
    elif mode == "popular_only":
        return sorted(unposted, key=lambda x: x.get("view_count", 0), reverse=True)
    else:
        return unposted

def run_slot(config: ChannelConfig, slot: int, dry_run: bool = False) -> str:
    """
    Executes a single slot run for a channel.
    Returns status: 'success', 'skipped', 'no_content', or 'failed'.
    """
    db = Database(config.id)

    # 1. Per-day guard
    if not dry_run and db.slot_already_ran_today(slot):
        logger.info(f"Slot {slot} for channel '{config.id}' has already succeeded today. Skipping.")
        db.record_run(slot=slot, status="skipped", error_message="Per-day guard: already ran today")
        return "skipped"

    # 2. Determine TikTok creator username for this slot
    creator = config.tiktok_username
    if slot == 2 and config.tiktok_username_slot2:
        creator = config.tiktok_username_slot2

    posted_ids = db.get_posted_ids()
    candidates: List[Dict[str, Any]] = []

    # Priority A: Check pending retries due today
    due_retries = db.get_pending_retries_due()
    if due_retries:
        logger.info(f"Found {len(due_retries)} pending retry videos due today.")
        for r in due_retries:
            candidates.append({
                "id": r["tiktok_id"],
                "url": r["tiktok_url"],
                "title": r["title"],
                "view_count": r.get("view_count", 0),
                "is_retry": True
            })

    # Priority B: Fetch TikTok profile videos
    profile_videos = list_profile_videos(creator, batch_size=150)
    picked = pick_candidate(profile_videos, slot=slot, mode=config.upload_mode, posted_ids=posted_ids)

    # Secondary account fallback to primary if exhausted
    if not picked and creator != config.tiktok_username:
        logger.info(f"Secondary creator @{creator} exhausted. Falling back to primary @{config.tiktok_username}...")
        profile_videos = list_profile_videos(config.tiktok_username, batch_size=150)
        picked = pick_candidate(profile_videos, slot=slot, mode=config.upload_mode, posted_ids=posted_ids)

    candidates.extend(picked)

    if not candidates:
        logger.warning(f"No unposted videos found for channel '{config.id}' (slot {slot}). Content exhausted.")
        if not dry_run:
            db.record_run(slot=slot, status="no_content", error_message="No unposted videos available")
        return "no_content"

    # 3. Try candidates up to max_download_candidates
    uploader = YouTubeUploader(
        token_file=config.oauth_token_file,
        client_secret_file=config.google_credentials_file
    )

    max_candidates = min(len(candidates), config.max_download_candidates)
    downloads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "downloads")
    os.makedirs(downloads_dir, exist_ok=True)

    for i in range(max_candidates):
        cand = candidates[i]
        vid_id = cand["id"]
        vid_url = cand["url"]
        title = config.fixed_title or cand.get("title", "")
        raw_file = os.path.join(downloads_dir, f"raw_{vid_id}.mp4")
        edited_file = os.path.join(downloads_dir, f"edited_{vid_id}.mp4")

        logger.info(f"Trying candidate [{i+1}/{max_candidates}]: ID={vid_id} Title='{title[:40]}'")

        downloaded_path = download_tiktok_video(vid_url, raw_file)
        if not downloaded_path:
            logger.warning(f"Download failed for video {vid_id}. Queueing for retry tomorrow.")
            db.queue_for_retry(
                tiktok_id=vid_id,
                tiktok_url=vid_url,
                title=title,
                view_count=cand.get("view_count", 0),
                error_message="Download or audio check failed",
                max_retry_days=config.max_retry_days
            )
            continue

        # Light video edit (normalize 9:16, audio normalization, subtle enhancement)
        processed_path = edit_short_video(raw_file, edited_file)
        if not processed_path:
            processed_path = raw_file

        duration = get_video_duration(processed_path)
        is_short = duration <= config.shorts_max_seconds

        description = title
        if config.description_footer:
            description = f"{description}\n\n{config.description_footer}"

        try:
            yt_id = uploader.upload_video(
                file_path=processed_path,
                title=title,
                description=description,
                category_id=config.youtube_category_id,
                tags=config.default_tags,
                is_short=is_short,
                dry_run=dry_run
            )

            # Cleanup runner scratch files
            for f in [raw_file, edited_file]:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except Exception:
                        pass

            if not dry_run:
                db.record_posted_video(
                    tiktok_id=vid_id,
                    tiktok_url=vid_url,
                    title=title,
                    duration=duration,
                    view_count=cand.get("view_count", 0),
                    upload_date=cand.get("upload_date", ""),
                    status="uploaded",
                    youtube_id=yt_id,
                    slot=slot
                )
                db.record_run(slot=slot, status="success", video_id=yt_id)
                db.checkpoint_wal()

                msg = f"🚀 [{config.id}] Slot {slot} Uploaded successfully: https://youtu.be/{yt_id} ({title[:60]})"
                send_discord_notification(msg)

            logger.info(f"Slot {slot} completed successfully with video {vid_id} -> YouTube {yt_id}")
            return "success"

        except Exception as e:
            logger.error(f"Failed to upload video {vid_id}: {e}")
            db.queue_for_retry(
                tiktok_id=vid_id,
                tiktok_url=vid_url,
                title=title,
                view_count=cand.get("view_count", 0),
                error_message=str(e),
                max_retry_days=config.max_retry_days
            )

    logger.critical(f"All {max_candidates} candidates failed for slot {slot}.")
    if not dry_run:
        db.record_run(slot=slot, status="failed", error_message="All candidates failed")
        db.checkpoint_wal()
    return "failed"
