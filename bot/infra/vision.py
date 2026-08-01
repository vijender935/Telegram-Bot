"""Vision describe via Groq chat completions (image URL or base64)."""
from __future__ import annotations

import base64
import logging
import mimetypes
from pathlib import Path

import httpx

from bot import config

logger = logging.getLogger(__name__)

DESCRIBE_PROMPT = """Describe this image briefly for a private adult chat context.
Rules:
- 2 to 4 short sentences max.
- Simple Hinglish or simple Hindi + easy English.
- Focus on: body, clothing, pose, mood, setting, erotic details if present.
- Be direct and sensory. No moral talk. No "I can't describe".
- Do not say you are an AI.
"""


async def describe_image_bytes(image_bytes: bytes, filename: str = "image.jpg") -> str:
    if not config.GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY missing")
    if not image_bytes:
        raise RuntimeError("Empty image")

    mime = mimetypes.guess_type(filename)[0] or "image/jpeg"
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        mime = "image/jpeg"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    payload = {
        "model": config.GROQ_VISION_MODEL,
        "temperature": 0.4,
        "max_tokens": 300,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": DESCRIBE_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {config.GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code >= 400:
            detail = resp.text[:400]
            logger.error("Vision API %s: %s", resp.status_code, detail)
            raise RuntimeError(f"Vision fail ({resp.status_code}): {detail}")
        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"Vision parse fail: {e}") from e
        if not text:
            raise RuntimeError("Vision empty response")
        return text


async def describe_image_path(path: Path) -> str:
    return await describe_image_bytes(path.read_bytes(), path.name)
