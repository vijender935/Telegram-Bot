"""
Image Enhancement Pipeline
--------------------------
Mode A — AI Regeneration   : Hugging Face img2img (FLUX.1-Kontext-dev) — FREE
Mode B — Faithful Upscale  : Real-ESRGAN via Replicate API
Mode C — Full Pipeline     : A → B (best quality)

Env vars needed:
  HF_TOKEN          — huggingface.co/settings/tokens (free account)
  REPLICATE_API_TOKEN — replicate.com (pay per use, ~$0.01/image)
"""

import asyncio
import base64
import io
import logging
import os
import time
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


# ── API Keys (env se aate hain — kabhi hardcode mat karo) ────────────────────
def _hf_token() -> str:
    k = os.getenv("HF_TOKEN", "")
    if not k:
        raise RuntimeError("HF_TOKEN env var not set! huggingface.co pe free account banao.")
    return k

def _replicate_token() -> str:
    k = os.getenv("REPLICATE_API_TOKEN", "")
    if not k:
        raise RuntimeError("REPLICATE_API_TOKEN env var not set!")
    return k


class EnhanceMode(str, Enum):
    REGENERATE = "regen"    # Mode A — HF img2img
    UPSCALE    = "upscale"  # Mode B — Real-ESRGAN
    FULL       = "full"     # Mode C — A phir B


# ─────────────────────────────────────────────────────────────────────────────
# MODE A — Hugging Face img2img (FLUX.1-Kontext-dev)
# FREE tier mein available — monthly credits milte hain
# ─────────────────────────────────────────────────────────────────────────────
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
    """
    Hugging Face Inference API se img2img — original image reference ke roop mein.
    FLUX.1-Kontext-dev model use hota hai — powerful image editing.
    Returns: Enhanced image bytes
    """
    b64_input = base64.b64encode(image_bytes).decode()

    payload = {
        "inputs": b64_input,
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

    # HF Inference API endpoint — img2img task
    url = "https://api-inference.huggingface.co/models/black-forest-labs/FLUX.1-Kontext-dev"

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

        # Model loading ho raha ho toh wait karo
        if resp.status_code == 503:
            wait = int(resp.headers.get("X-Wait-For-Model", "20"))
            logger.info("HF model loading, waiting %ds...", wait)
            await asyncio.sleep(min(wait, 30))
            resp = await client.post(url, json=payload, headers=headers)

        resp.raise_for_status()

    # Response = raw image bytes (JPEG/PNG)
    return resp.content


# ─────────────────────────────────────────────────────────────────────────────
# MODE B — Real-ESRGAN via Replicate (faithful upscale, identity preserve)
# ─────────────────────────────────────────────────────────────────────────────
async def upscale_image(
    image_bytes: bytes,
    scale: int = 4,
    face_enhance: bool = True,
) -> bytes:
    """
    Real-ESRGAN via Replicate — original identity preserve karta hai.
    Sirf resolution + sharpness badhta hai, face same rehta hai.
    """
    b64 = base64.b64encode(image_bytes).decode()
    image_uri = f"data:image/jpeg;base64,{b64}"

    headers = {
        "Authorization": f"Token {_replicate_token()}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }

    payload = {
        "version": "42fed1c4974146d4d2414e2be2c5277c7fcf05fcc3a73abf41610695738c1d7b",
        "input": {
            "image": image_uri,
            "scale": scale,
            "face_enhance": face_enhance,
        },
    }

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            "https://api.replicate.com/v1/predictions",
            json=payload,
            headers=headers,
        )
        resp.raise_for_status()
        prediction = resp.json()

    # Synchronous response mila
    output = prediction.get("output")
    if output:
        img_url = output if isinstance(output, str) else output[0]
        return await _download_url(img_url)

    # Poll karo
    return await _poll_replicate(prediction["id"], headers)


async def _poll_replicate(pred_id: str, headers: dict, max_wait: int = 120) -> bytes:
    url = f"https://api.replicate.com/v1/predictions/{pred_id}"
    deadline = time.time() + max_wait

    async with httpx.AsyncClient(timeout=30.0) as client:
        while time.time() < deadline:
            await asyncio.sleep(3)
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            status = data.get("status")

            if status == "succeeded":
                output = data.get("output")
                img_url = output if isinstance(output, str) else output[0]
                return await _download_url(img_url)

            if status in ("failed", "canceled"):
                raise RuntimeError(f"Replicate {status}: {data.get('error')}")

    raise TimeoutError(f"Replicate prediction {pred_id} timed out after {max_wait}s")


async def _download_url(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return r.content


# ─────────────────────────────────────────────────────────────────────────────
# MODE C — Full Pipeline (A + B)
# ─────────────────────────────────────────────────────────────────────────────
async def full_pipeline(
    image_bytes: bytes,
    prompt: str | None = None,
    scale: int = 4,
) -> bytes:
    """
    Best quality:
    Original → HF AI Regeneration → Real-ESRGAN 4x Upscale → Final
    """
    logger.info("Full pipeline: Step 1/2 — HF AI Regeneration...")
    kwargs = {}
    if prompt:
        kwargs["prompt"] = prompt
    regen = await regenerate_image(image_bytes, **kwargs)

    logger.info("Full pipeline: Step 2/2 — Real-ESRGAN Upscale...")
    final = await upscale_image(regen, scale=scale, face_enhance=True)
    return final


# ─────────────────────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────────────────────
async def enhance_image(
    image_bytes: bytes,
    mode: EnhanceMode = EnhanceMode.FULL,
    prompt: str | None = None,
    scale: int = 4,
    strength: float = 0.55,  # kept for API compat, HF uses guidance_scale instead
) -> tuple[bytes, str]:
    """
    Returns: (enhanced_bytes, description_str)
    """
    if mode == EnhanceMode.REGENERATE:
        kwargs = {}
        if prompt:
            kwargs["prompt"] = prompt
        result = await regenerate_image(image_bytes, **kwargs)
        desc = "🎨 AI Regeneration complete — face/details reconstructed via HF FLUX"

    elif mode == EnhanceMode.UPSCALE:
        result = await upscale_image(image_bytes, scale=scale, face_enhance=True)
        desc = f"📐 Real-ESRGAN {scale}x Upscale complete — identity faithfully preserved"

    else:  # FULL
        result = await full_pipeline(image_bytes, prompt=prompt, scale=scale)
        desc = (
            f"🔥 Full Pipeline complete!\n"
            f"Step 1: HF FLUX AI Regeneration (beautify + reconstruct)\n"
            f"Step 2: Real-ESRGAN {scale}x Upscale (sharpen + enlarge)"
        )

    return result, desc
