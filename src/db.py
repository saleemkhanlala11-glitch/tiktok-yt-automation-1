import os
import sqlite3
from datetime import datetime, timezone
from typing import Set, List, Optional, Dict, Any

def get_db_path(channel_id: str) -> str:
    data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, f"{channel_id}.db")

class Database:
    def __init__(self, channel_id: str):
        self.channel_id = channel_id
        self.db_path = get_db_path(channel_id)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS posted_videos (
                    tiktok_id TEXT PRIMARY KEY,
                    tiktok_url TEXT,
                    title TEXT,
                    duration REAL,
                    view_count INTEGER DEFAULT 0,
                    upload_date TEXT,
                    status TEXT NOT NULL,
                    youtube_id TEXT,
                    posted_at TEXT,
                    retry_count INTEGER DEFAULT 0,
                    next_retry_date TEXT,
                    last_error TEXT,
                    slot INTEGER
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    slot INTEGER NOT NULL,
                    channel_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    video_id TEXT,
                    error_message TEXT,
                    timestamp TEXT NOT NULL
                );
            """)
            conn.commit()

    def slot_already_ran_today(self, slot: int, date_str: Optional[str] = None) -> bool:
        """Per-day guard: returns True if runs table has a 'success' status for today + slot."""
        if not date_str:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT 1 FROM runs
                WHERE channel_id = ? AND slot = ? AND date = ? AND status = 'success'
                LIMIT 1;
            """, (self.channel_id, slot, date_str))
            return cur.fetchone() is not None

    def get_posted_ids(self) -> Set[str]:
        """A video counts as posted if status is uploaded, failed_permanent, skipped, or pending_retry."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT tiktok_id FROM posted_videos
                WHERE status IN ('uploaded', 'failed_permanent', 'skipped', 'pending_retry');
            """)
            return {row["tiktok_id"] for row in cur.fetchall()}

    def get_pending_retries_due(self, today_str: Optional[str] = None) -> List[Dict[str, Any]]:
        if not today_str:
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM posted_videos
                WHERE status = 'pending_retry' AND next_retry_date <= ?
                ORDER BY retry_count ASC;
            """, (today_str,))
            return [dict(row) for row in cur.fetchall()]

    def record_run(self, slot: int, status: str, video_id: Optional[str] = None,
                   error_message: Optional[str] = None, date_str: Optional[str] = None):
        utc_now = datetime.now(timezone.utc)
        if not date_str:
            date_str = utc_now.strftime("%Y-%m-%d")
        ts_str = utc_now.isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO runs (date, slot, channel_id, status, video_id, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?);
            """, (date_str, slot, self.channel_id, status, video_id, error_message, ts_str))
            conn.commit()

    def record_posted_video(self, tiktok_id: str, tiktok_url: str, title: str,
                            duration: float, view_count: int, upload_date: str,
                            status: str, youtube_id: Optional[str] = None,
                            slot: Optional[int] = None, last_error: Optional[str] = None):
        now_ts = datetime.now(timezone.utc).isoformat()
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO posted_videos (
                    tiktok_id, tiktok_url, title, duration, view_count,
                    upload_date, status, youtube_id, posted_at, slot, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tiktok_id) DO UPDATE SET
                    status=excluded.status,
                    youtube_id=COALESCE(excluded.youtube_id, posted_videos.youtube_id),
                    posted_at=excluded.posted_at,
                    slot=COALESCE(excluded.slot, posted_videos.slot),
                    last_error=excluded.last_error;
            """, (tiktok_id, tiktok_url, title, duration, view_count,
                  upload_date, status, youtube_id, now_ts, slot, last_error))
            conn.commit()

    def queue_for_retry(self, tiktok_id: str, tiktok_url: str, title: str,
                        view_count: int, error_message: str, max_retry_days: int = 7):
        utc_now = datetime.now(timezone.utc)
        today_str = utc_now.strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT retry_count FROM posted_videos WHERE tiktok_id = ?", (tiktok_id,))
            row = cur.fetchone()
            current_retries = row["retry_count"] if row else 0
            new_retries = current_retries + 1

            if new_retries >= max_retry_days:
                status = "failed_permanent"
                next_retry = None
            else:
                status = "pending_retry"
                # Tomorrow
                from datetime import timedelta
                next_retry = (utc_now + timedelta(days=1)).strftime("%Y-%m-%d")

            conn.execute("""
                INSERT INTO posted_videos (
                    tiktok_id, tiktok_url, title, view_count, status,
                    retry_count, next_retry_date, last_error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tiktok_id) DO UPDATE SET
                    status=excluded.status,
                    retry_count=excluded.retry_count,
                    next_retry_date=excluded.next_retry_date,
                    last_error=excluded.last_error;
            """, (tiktok_id, tiktok_url, title, view_count, status,
                  new_retries, next_retry, error_message))
            conn.commit()

    def checkpoint_wal(self):
        """Forces SQLite WAL log to merge back into main .db file for clean git commit."""
        with self._get_connection() as conn:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
