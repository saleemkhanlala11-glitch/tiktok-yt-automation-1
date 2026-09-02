import os
import json
import logging
import subprocess
from typing import Optional, Dict, Any

logger = logging.getLogger("video_converter")

def get_video_metadata(file_path: str) -> Dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_streams",
        "-show_format",
        file_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(res.stdout)
    except Exception as e:
        logger.error(f"Failed to probe {file_path}: {e}")
        return {}

def get_video_duration(file_path: str) -> float:
    meta = get_video_metadata(file_path)
    fmt = meta.get("format", {})
    if "duration" in fmt:
        return float(fmt["duration"])
    for s in meta.get("streams", []):
        if s.get("codec_type") == "video" and "duration" in s:
            return float(s["duration"])
    return 0.0

def edit_short_video(input_path: str, output_path: str) -> Optional[str]:
    """
    Performs light editing and optimization on the video:
    - Scales / pads to standard 1080x1920 (9:16 vertical Short)
    - Applies subtle micro-enhancement (contrast/saturation boost) for clean mobile rendering
    - Normalizes audio loudness for crisp mobile listening
    - Re-encodes using H.264 + AAC 48kHz with +faststart
    """
    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        return None

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

    # FFmpeg filter:
    # 1. scale to fit within 1080x1920 keeping aspect ratio
    # 2. pad to 1080:1920 if needed
    # 3. slight color/contrast tuning: contrast=1.02, saturation=1.03
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,"
        "eq=contrast=1.02:brightness=0.01:saturation=1.03"
    )

    # Audio filter:
    # Gentle loudness normalization (EBU R128)
    audio_filter = "loudnorm=I=-16:TP=-1.5:LRA=11"

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "21",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-movflags", "+faststart",
        output_path
    ]

    logger.info(f"Applying light video editing with ffmpeg: {input_path} -> {output_path}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info("Video editing completed successfully.")
            return output_path
        else:
            logger.warning(f"FFmpeg failed with returncode {res.returncode}: {res.stderr[-300:]}")
            # Fallback to simple copy if complex filter failed
            return _fallback_reencode(input_path, output_path)
    except Exception as e:
        logger.error(f"Exception during video editing: {e}")
        return _fallback_reencode(input_path, output_path)

def _fallback_reencode(input_path: str, output_path: str) -> Optional[str]:
    logger.info(f"Attempting fallback re-encode for {input_path}")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-c:a", "aac",
        "-movflags", "+faststart",
        output_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(output_path):
        return output_path
    return input_path
