import logging
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_MIME = {
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".mp3": "audio/mpeg",
    ".mp4": "audio/mp4",
    ".m4a": "audio/mp4",
    ".wav": "audio/wav",
    ".webm": "audio/webm",
    ".flac": "audio/flac",
    ".mpeg": "audio/mpeg",
    ".mpga": "audio/mpeg",
}


def _mime_for(filename: str) -> str:
    low = filename.lower()
    for ext, mime in _MIME.items():
        if low.endswith(ext):
            return mime
    return "application/octet-stream"


async def transcribe_audio(file_bytes: bytes, filename: str, api_key: str) -> str:
    """Groq Whisper transcription with correct MIME + clear errors."""
    if not api_key:
        raise RuntimeError("GROQ_API_KEY missing")
    if not file_bytes:
        raise RuntimeError("Empty audio")

    mime = _mime_for(filename)
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, file_bytes, mime)},
            data={
                "model": "whisper-large-v3-turbo",
                "response_format": "text",
            },
        )
        if resp.status_code >= 400:
            detail = resp.text[:300]
            logger.error("Whisper API %s: %s", resp.status_code, detail)
            raise RuntimeError(f"Whisper fail ({resp.status_code}): {detail}")
        text = resp.text.strip()
        if not text:
            raise RuntimeError("Transcript empty — voice clear nahi thi shayad")
        return text


def ffmpeg_available() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def extract_audio_from_video(video_bytes: bytes) -> bytes:
    """Video → mp3 via ffmpeg. Raises clear error if ffmpeg missing."""
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg server pe install nahi hai. "
            "Render Build Command mein add karo: apt-get update && apt-get install -y ffmpeg"
        )

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
        vf.write(video_bytes)
        vf_path = vf.name
    out_path = vf_path.replace(".mp4", ".mp3")
    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", vf_path, "-vn", "-ar", "16000",
             "-ac", "1", "-b:a", "64k", out_path],
            capture_output=True,
        )
        if result.returncode != 0:
            err = (result.stderr or b"").decode("utf-8", errors="ignore")[-400:]
            raise RuntimeError(f"ffmpeg fail: {err}")
        return Path(out_path).read_bytes()
    finally:
        Path(vf_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
