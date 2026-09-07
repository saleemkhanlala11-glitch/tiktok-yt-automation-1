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
        try:
            return float(fmt["duration"])
        except (ValueError, TypeError):
            pass
    for s in meta.get("streams", []):
        if s.get("codec_type") == "video" and "duration" in s:
            try:
                return float(s["duration"])
            except (ValueError, TypeError):
                pass
    return 0.0

def edit_short_video(input_path: str, output_path: str) -> Optional[str]:
    """
    Performs automated video editing and visual/audio enhancement:
    - Scales / pads to standard 1080x1920 (9:16 vertical Short)
    - Applies subtle visual enhancement (contrast=1.04, saturation=1.06, sharpness boost)
    - Normalizes audio loudness with EBU R128 standard (loudnorm)
    - Adds smooth intro/outro transitions (0.3s video & audio fade)
    - Re-encodes using H.264 + AAC 48kHz with +faststart
    """
    if not os.path.exists(input_path):
        logger.error(f"Input file not found: {input_path}")
        return None

    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    duration = get_video_duration(input_path)

    # Base video filters: scale/pad to 1080x1920, color enhancement, slight unsharp mask
    vf_parts = [
        "scale=1080:1920:force_original_aspect_ratio=decrease",
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "eq=contrast=1.04:brightness=0.01:saturation=1.06",
        "unsharp=3:3:0.4:3:3:0.0"
    ]

    af_parts = [
        "loudnorm=I=-16:TP=-1.5:LRA=11"
    ]

    # Add gentle fade in/out if duration is known and >= 3 seconds
    if duration >= 3.0:
        fade_out_start = max(0.0, duration - 0.3)
        vf_parts.append(f"fade=t=in:st=0:d=0.25,fade=t=out:st={fade_out_start:.2f}:d=0.25")
        af_parts.append(f"afade=t=in:st=0:d=0.25,afade=t=out:st={fade_out_start:.2f}:d=0.25")

    video_filter = ",".join(vf_parts)
    audio_filter = ",".join(af_parts)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-movflags", "+faststart",
        output_path
    ]

    logger.info(f"Applying video editing & enhancement with FFmpeg: {input_path} -> {output_path}")
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            logger.info("Video editing and enhancement completed successfully.")
            return output_path
        else:
            logger.warning(f"FFmpeg filter failed with code {res.returncode}: {res.stderr[-300:]}")
            return _fallback_reencode(input_path, output_path)
    except Exception as e:
        logger.error(f"Exception during video editing: {e}")
        return _fallback_reencode(input_path, output_path)

def _fallback_reencode(input_path: str, output_path: str) -> Optional[str]:
    logger.info(f"Attempting fallback safe re-encode for {input_path}")
    cmd = [
        "ffmpeg",
        "-y",
        "-i", input_path,
        "-vf", "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-movflags", "+faststart",
        output_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            logger.info("Fallback re-encode succeeded.")
            return output_path
        else:
            logger.error(f"Fallback re-encode failed: {res.stderr[-300:]}")
            return None
    except Exception as e:
        logger.error(f"Exception in fallback re-encode: {e}")
        return None
