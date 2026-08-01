import logging
import subprocess
import tempfile
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)


async def transcribe_audio(file_bytes: bytes, filename: str, api_key: str) -> str:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": (filename, file_bytes, "audio/mpeg")},
            data={"model": "whisper-large-v3-turbo", "response_format": "text"},
        )
        resp.raise_for_status()
        return resp.text.strip()


def extract_audio_from_video(video_bytes: bytes) -> bytes:
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
        vf.write(video_bytes)
        vf_path = vf.name
    out_path = vf_path.replace(".mp4", ".mp3")
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", vf_path, "-vn", "-ar", "16000",
             "-ac", "1", "-b:a", "64k", out_path],
            capture_output=True, check=True,
        )
        return Path(out_path).read_bytes()
    finally:
        Path(vf_path).unlink(missing_ok=True)
        Path(out_path).unlink(missing_ok=True)
