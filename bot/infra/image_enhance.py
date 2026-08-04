"""
Image Enhancement — FREE only
-----------------------------
Mode A — AI Regeneration : Hugging Face Inference API (FLUX.1-Kontext-dev)
Mode B — Upscale         : Local Pillow (LANCZOS) — no paid API
Mode C — Full            : A → B

Env:
  HF_TOKEN — huggingface.co/settings/tokens (free)
"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from enum import Enum

import httpx
from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

HF_MODEL_URL = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-Kontext-dev"


def _hf_token() -> str:
    k = os.getenv("HF_TOKEN", "").strip()
    if not k:
        raise RuntimeError(
            "HF_TOKEN missing. Free token: https://huggingface.co/settings/tokens"
        )
    return k


class EnhanceMode(str, Enum):
    REGENERATE = "regen"
    UPSCALE = "upscale"
    FULL = "full"


async def regenerate_image(
    image_bytes: bytes,
    prompt: str = (
        "high quality photo, beautiful face, smooth clean skin, "
        "sharp details, professional lighting, 4K resolution, "
        "detailed hair strands, natural look, face enhancement"
    ),
    negative_prompt: str = (
        "blurry, low quality, pixelated, noise, artifacts, "
        "deformed face, overexposed, watermark"
    ),
    guidance_scale: float = 7.5,
    steps: int = 28,
) -> bytes:
    """HF img2img — free tier (cold start possible)."""
    payload = {
        "inputs": base64.b64encode(image_bytes).decode(),
        "parameters": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "guidance_scale": guidance_scale,
            "num_inference_steps": steps,
        },
    }
    headers = {
        "Authorization": f"Bearer {_hf_token()}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(HF_MODEL_URL, json=payload, headers=headers)

        if resp.status_code == 503:
            wait = int(resp.headers.get("X-Wait-For-Model", "25"))
            logger.info("HF model loading, wait %ss", wait)
            await asyncio.sleep(min(wait, 45))
            resp = await client.post(HF_MODEL_URL, json=payload, headers=headers)

        if resp.status_code == 402:
            raise RuntimeError(
                "HF free quota / payment issue. Naya free token try karo ya baad mein."
            )
        if resp.status_code >= 400:
            detail = (resp.text or "")[:300]
            raise RuntimeError(f"HF error {resp.status_code}: {detail}")

        ctype = resp.headers.get("content-type", "")
        if "application/json" in ctype:
            # sometimes JSON error body
            raise RuntimeError(f"HF JSON response: {resp.text[:300]}")
        return resp.content


def upscale_image_local(image_bytes: bytes, scale: int = 2) -> bytes:
    """Free local upscale + mild sharpen (no Replicate)."""
    scale = max(2, min(int(scale or 2), 4))
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    w, h = img.size
    img = img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=2))
    img = ImageEnhance.Sharpness(img).enhance(1.15)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


async def upscale_image(
    image_bytes: bytes,
    scale: int = 2,
    face_enhance: bool = True,  # ignored — free local path
) -> bytes:
    return await asyncio.to_thread(upscale_image_local, image_bytes, scale)


async def full_pipeline(
    image_bytes: bytes,
    prompt: str | None = None,
    scale: int = 2,
) -> bytes:
    kwargs = {}
    if prompt:
        kwargs["prompt"] = prompt
    regen = await regenerate_image(image_bytes, **kwargs)
    return await upscale_image(regen, scale=scale)


async def enhance_image(
    image_bytes: bytes,
    mode: EnhanceMode = EnhanceMode.REGENERATE,
    prompt: str | None = None,
    scale: int = 2,
    strength: float = 0.55,
) -> tuple[bytes, str]:
    mode = EnhanceMode.REGENERATE  # force free-only UI
    if mode == EnhanceMode.REGENERATE:
        kwargs = {}
        if prompt:
            kwargs["prompt"] = prompt
        result = await regenerate_image(image_bytes, **kwargs)
        desc = "🎨 AI Regen (Hugging Face FREE)"

    elif mode == EnhanceMode.UPSCALE:
        result = await upscale_image(image_bytes, scale=scale)
        desc = f"📐 Local {scale}x upscale (FREE — no Replicate)"

    else:
        result = await full_pipeline(image_bytes, prompt=prompt, scale=scale)
        desc = (
            "🔥 Full FREE pipeline\n"
            "1) HF AI Regen\n"
            f"2) Local {scale}x upscale"
        )

    return result, desc
