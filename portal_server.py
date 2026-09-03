import os
import sys
import json
import sqlite3
import yaml
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

PORT = 5000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTAL_DIR = os.path.join(BASE_DIR, "portal")

def get_db_path(channel_id):
    return os.path.join(BASE_DIR, "data", f"{channel_id}.db")

def load_channels():
    config_path = os.path.join(BASE_DIR, "channels.yaml")
    if not os.path.exists(config_path):
        return []
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("channels", []) if data else []
    except Exception as e:
        print(f"Error reading channels.yaml: {e}")
        return []

def get_channel_data(channel_id):
    db_path = get_db_path(channel_id)
    if not os.path.exists(db_path):
        return {"runs": [], "posted_videos": [], "stats": {"total_posted": 0, "total_runs": 0}}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Runs
        cur.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 50;")
        runs = [dict(r) for r in cur.fetchall()]

        # Posted videos
        cur.execute("SELECT * FROM posted_videos ORDER BY rowid DESC LIMIT 50;")
        posted = [dict(r) for r in cur.fetchall()]

        # Aggregates
        cur.execute("SELECT COUNT(*) as count FROM posted_videos WHERE status = 'uploaded';")
        uploaded_count = cur.fetchone()["count"]

        conn.close()
        return {
            "runs": runs,
            "posted_videos": posted,
            "stats": {
                "total_uploaded": uploaded_count,
                "total_runs": len(runs)
            }
        }
    except Exception as e:
        print(f"Error querying db for {channel_id}: {e}")
        return {"runs": [], "posted_videos": [], "stats": {"total_uploaded": 0, "total_runs": 0}}

class PortalHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PORTAL_DIR, **kwargs)

    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/channels":
            channels = load_channels()
            response_channels = []
            today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

            for ch in channels:
                ch_id = ch.get("id", "")
                data = get_channel_data(ch_id)
                # Check today's slot statuses
                runs_today = [r for r in data["runs"] if r.get("date") == today_str]
                slot1_success = any(r.get("slot") == 1 and r.get("status") == "success" for r in runs_today)
                slot2_success = any(r.get("slot") == 2 and r.get("status") == "success" for r in runs_today)

                ch_info = dict(ch)
                ch_info["data"] = data
                ch_info["today_status"] = {
                    "slot_1": "success" if slot1_success else "pending",
                    "slot_2": "success" if slot2_success else "pending",
                    "uploaded_today": sum(1 for r in runs_today if r.get("status") == "success")
                }
                response_channels.append(ch_info)

            self._send_json({"status": "ok", "channels": response_channels, "timestamp": datetime.now(timezone.utc).isoformat()})
            return

        elif path.startswith("/api/channel/"):
            ch_id = path.split("/")[-1]
            channels = load_channels()
            target = next((c for c in channels if c.get("id") == ch_id), None)
            if not target:
                self._send_json({"error": "Channel not found"}, status=404)
                return
            data = get_channel_data(ch_id)
            ch_info = dict(target)
            ch_info["data"] = data
            self._send_json({"status": "ok", "channel": ch_info})
            return

        elif path == "/api/summary":
            channels = load_channels()
            total_uploads = 0
            total_active = sum(1 for c in channels if c.get("enabled", True))
            for ch in channels:
                data = get_channel_data(ch.get("id", ""))
                total_uploads += data["stats"]["total_uploaded"]

            self._send_json({
                "status": "ok",
                "total_channels": len(channels),
                "active_channels": total_active,
                "total_videos_uploaded": total_uploads,
                "system_time_utc": datetime.now(timezone.utc).isoformat()
            })
            return

        return super().do_GET()

def run_server():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.makedirs(PORTAL_DIR, exist_ok=True)
    server_address = ("", PORT)
    httpd = HTTPServer(server_address, PortalHandler)
    print("======================================================")
    print(">> YouTube Automation Mobile Portal Server Running")
    print(f">> Local URL: http://localhost:{PORT}")
    print(f">> Mobile Network URL: http://<your-pc-ip>:{PORT}")
    print("======================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping portal server...")
        httpd.server_close()

if __name__ == "__main__":
    run_server()
