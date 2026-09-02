import os
import yaml
from dataclasses import dataclass, field
from typing import List, Dict, Optional

VALID_UPLOAD_MODES = {"popular_split", "short_only", "popular_only", "sequence"}

@dataclass
class ChannelConfig:
    id: str
    tiktok_username: str
    youtube_channel_name: str
    owner_email: str
    google_credentials_file: str
    oauth_token_file: str
    videos_per_day: int = 2
    description_footer: str = ""
    default_tags: List[str] = field(default_factory=list)
    youtube_category_id: str = "22"
    enabled: bool = True
    max_retry_days: int = 7
    shorts_max_seconds: int = 180
    upload_mode: str = "popular_split"
    max_download_candidates: int = 20
    tiktok_username_slot2: Optional[str] = None
    slot_publish_times_utc: Dict[int, str] = field(default_factory=dict)
    min_upload_date: Optional[str] = None
    min_backlog_for_slot1: Optional[int] = None
    fixed_title: Optional[str] = None

def load_channels_config(config_path: str = "channels.yaml") -> List[ChannelConfig]:
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    if not raw or "channels" not in raw:
        raise ValueError("Invalid channels.yaml: missing 'channels' key")

    channels = []
    for item in raw["channels"]:
        mode = item.get("upload_mode", "popular_split")
        if mode not in VALID_UPLOAD_MODES:
            raise ValueError(f"Channel {item.get('id')}: invalid upload_mode '{mode}'. Whitelist: {VALID_UPLOAD_MODES}")

        slot_times = item.get("slot_publish_times_utc", {})
        parsed_slots = {int(k): str(v) for k, v in slot_times.items()}

        cfg = ChannelConfig(
            id=str(item["id"]),
            tiktok_username=str(item["tiktok_username"]).lstrip("@"),
            youtube_channel_name=str(item.get("youtube_channel_name", "")),
            owner_email=str(item.get("owner_email", "")),
            google_credentials_file=str(item.get("google_credentials_file", f"credentials/{item['id']}_client_secret.json")),
            oauth_token_file=str(item.get("oauth_token_file", f"tokens/{item['id']}_token.json")),
            videos_per_day=int(item.get("videos_per_day", 2)),
            description_footer=str(item.get("description_footer", "")),
            default_tags=list(item.get("default_tags", [])),
            youtube_category_id=str(item.get("youtube_category_id", "22")),
            enabled=bool(item.get("enabled", True)),
            max_retry_days=int(item.get("max_retry_days", 7)),
            shorts_max_seconds=int(item.get("shorts_max_seconds", 180)),
            upload_mode=mode,
            max_download_candidates=int(item.get("max_download_candidates", 20)),
            tiktok_username_slot2=item.get("tiktok_username_slot2"),
            slot_publish_times_utc=parsed_slots,
            min_upload_date=item.get("min_upload_date"),
            min_backlog_for_slot1=item.get("min_backlog_for_slot1"),
            fixed_title=item.get("fixed_title")
        )
        channels.append(cfg)

    return channels

def get_channel_config(channel_id: str, config_path: str = "channels.yaml") -> ChannelConfig:
    channels = load_channels_config(config_path)
    for ch in channels:
        if ch.id == channel_id:
            return ch
    raise ValueError(f"Channel with id '{channel_id}' not found in {config_path}")
