import argparse
import sys
from src.orchestrator import run_pipeline

def main():
    parser = argparse.ArgumentParser(description="TikTok to YouTube Automation Runner")
    parser.add_argument("--slot", type=int, required=True, choices=[1, 2], help="Slot number (1 or 2)")
    parser.add_argument("--channel", type=str, default=None, help="Channel ID (e.g. channel_1)")
    parser.add_argument("--dry-run", action="store_true", help="Run without actually uploading to YouTube")

    args = parser.parse_args()
    code = run_pipeline(channel_id=args.channel, slot=args.slot, dry_run=args.dry_run)
    sys.exit(code)

if __name__ == "__main__":
    main()
