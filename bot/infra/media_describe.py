"""Describe images and videos (via frames) for chat context."""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from bot.infra.vision import describe_image_bytes, describe_image_path
from bot.infra.transcribe import ffmpeg_available

logger = logging.getLogger(__name__)

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
_VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"}


def is_image(name: str) -> bool:
    return Path(name).suffix.lower() in _IMAGE_EXT


def is_video(name: str) -> bool:
    return Path(name).suffix.lower() in _VIDEO_EXT


def _extract_frames(video_path: Path, max_frames: int = 3) -> list[bytes]:
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg missing — cannot describe video")
    frames: list[bytes] = []
    with tempfile.TemporaryDirectory() as td:
        out_pattern = str(Path(td) / "frame_%02d.jpg")
        # 1 fps, scale down for vision cost/latency
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", "fps=1,scale=640:-1",
            "-frames:v", str(max_frames),
            out_pattern,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            err = (result.stderr or b"").decode("utf-8", errors="ignore")[-300:]
            raise RuntimeError(f"ffmpeg frames fail: {err}")
        for p in sorted(Path(td).glob("frame_*.jpg")):
            frames.append(p.read_bytes())
    return frames


async def describe_media_path(path: Path) -> tuple[str, str]:
    """Return (type, description). type is image|video|other."""
    name = path.name
    if is_image(name):
        desc = await describe_image_path(path)
        return "image", desc

    if is_video(name):
        frames = _extract_frames(path, max_frames=3)
        if not frames:
            return "video", "video file (no frames extracted)"
        parts = []
        for i, fb in enumerate(frames, 1):
            try:
                d = await describe_image_bytes(fb, f"frame_{i}.jpg")
                parts.append(f"Scene {i}: {d}")
            except Exception:
                logger.exception("frame describe failed")
        if not parts:
            return "video", "hot video (description failed)"
        return "video", " | ".join(parts)

    return "other", f"file: {name}"
