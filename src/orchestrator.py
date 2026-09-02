import os
import sys
import logging
from typing import Optional

from .config import load_channels_config, get_channel_config
from .channel_runner import run_slot

logger = logging.getLogger("orchestrator")

def setup_logging(logs_dir: str = "logs"):
    os.makedirs(logs_dir, exist_ok=True)
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(logs_dir, "run.log"), encoding="utf-8")
        ]
    )

def run_pipeline(channel_id: Optional[str], slot: int, dry_run: bool = False) -> int:
    setup_logging()
    logger.info(f"Starting automation run: channel={channel_id or 'all'}, slot={slot}, dry_run={dry_run}")

    if channel_id:
        channels = [get_channel_config(channel_id)]
    else:
        channels = [ch for ch in load_channels_config() if ch.enabled]

    exit_code = 0
    for ch in channels:
        logger.info(f"--- Processing channel: {ch.id} (@{ch.tiktok_username}) ---")
        try:
            status = run_slot(ch, slot=slot, dry_run=dry_run)
            logger.info(f"Channel {ch.id} finished with status: {status}")
            if status == "failed":
                exit_code = 1
        except Exception as e:
            logger.exception(f"Unhandled exception while processing {ch.id}: {e}")
            exit_code = 1

    return exit_code
