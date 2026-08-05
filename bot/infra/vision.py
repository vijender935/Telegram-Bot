"""Vision describe via Groq chat completions (image URL or base64)."""
from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path

import httpx

from bot import config

logger = logging.getLogger(__name__)

DESCRIBE_PROMPT = """Describe this image for a private, flirty Hinglish chat.
Rules:
- 2 to 4 short sentences. Use Hinglish (Hindi + English).
- Be sensory and a bit teasing. If it's a person, compliment their vibe, pose, or what they're wearing in a flirty way.
- Focus on: mood, lighting, clothing (or lack of), and the 'energy' of the photo.
- Don't just list items; talk like you're looking at the photo with them.
- No AI disclaimers. No moralizing.
- Example: "Wah, yeh black dress toh kaafi hot lag rahi hai tumpe. Lighting bhi ekdum perfect hai, mood bana rahi hai..."
"""

# 429 rate limit pe retry delays (seconds)
_RETRY_DELAYS = [20, 40]


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

    last_error: Exception | None = None
    attempts = [None] + _RETRY_DELAYS  # first attempt + retries

    for attempt, delay in enumerate(attempts):
        if delay:
            logger.warning("Vision rate limit — %ss baad retry (%d/%d)…", delay, attempt, len(attempts) - 1)
            await asyncio.sleep(delay)

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {config.GROQ_API_KEY}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )

            if resp.status_code == 429:
                # Rate limit — retry with backoff
                detail = resp.text[:200]
                logger.warning("Vision 429 rate limit (attempt %d): %s", attempt + 1, detail)
                last_error = RuntimeError(f"Vision rate limit (429): thodi der baad try karo")
                continue  # next retry

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

        except RuntimeError:
            raise  # non-429 errors seedha raise
        except Exception as e:
            raise RuntimeError(f"Vision request fail: {e}") from e

    # Sab retries exhaust — last error raise karo
    raise last_error or RuntimeError("Vision: all retries failed")


async def describe_image_path(path: Path) -> str:
    return await describe_image_bytes(path.read_bytes(), path.name)
