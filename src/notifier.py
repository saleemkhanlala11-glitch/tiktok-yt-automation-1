import os
import logging
import requests
from typing import Optional

logger = logging.getLogger("notifier")

def send_discord_notification(message: str, webhook_url: Optional[str] = None):
    url = webhook_url or os.environ.get("DISCORD_WEBHOOK_URL")
    if not url:
        return

    try:
        payload = {"content": message}
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code not in (200, 204):
            logger.warning(f"Failed to post to Discord webhook: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.warning(f"Error sending Discord notification: {e}")
