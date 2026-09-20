import io
import json
import logging

from PIL import Image, UnidentifiedImageError
from telegram import Update

logger = logging.getLogger(__name__)


def extract_r2_keys(value: object) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    def add(candidate: object) -> None:
        if not isinstance(candidate, str) or not candidate or candidate in seen:
            return
        seen.add(candidate)
        found.append(candidate)

    def walk(item: object) -> None:
        if isinstance(item, str):
            raw = item.strip()
            if raw.startswith("{") or raw.startswith("["):
                try:
                    walk(json.loads(raw))
                except json.JSONDecodeError:
                    pass
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                walk(child)
            return
        if isinstance(item, dict):
            for key_name in ("r2_key", "r2Key"):
                add(item.get(key_name))
            metadata = item.get("metadata")
            if metadata is not None:
                walk(metadata)
            for key_name in ("matches", "images", "results", "content"):
                child = item.get(key_name)
                if child is not None:
                    walk(child)
            return
        content = getattr(item, "content", None)
        if content is not None and content is not item:
            walk(content)

    walk(value)
    return found


async def send_mcp_images(
    update: Update,
    images: list[tuple[bytes, str]],
    caption: str | None = None,
) -> int:
    sent = 0
    for index, (data, mime_type) in enumerate(images, start=1):
        if not data:
            continue

        filename = f"cloudflare_image_{index}.jpg"
        try:
            with Image.open(io.BytesIO(data)) as source:
                source.load()
                width, height = source.size
                if width <= 0 or height <= 0:
                    raise ValueError("invalid image dimensions")
                if source.mode in ("RGBA", "LA", "P"):
                    rgba = source.convert("RGBA")
                    background = Image.new("RGB", rgba.size, "white")
                    background.paste(rgba, mask=rgba.getchannel("A"))
                    normalized = background
                else:
                    normalized = source.convert("RGB")

                buffer = io.BytesIO()
                normalized.save(buffer, format="JPEG", quality=92, optimize=True)
                payload = buffer.getvalue()

            if len(payload) > 10 * 1024 * 1024:
                await update.message.reply_document(
                    document=io.BytesIO(payload),
                    filename=filename,
                    caption=caption if sent == 0 else None,
                )
            else:
                await update.message.reply_photo(
                    photo=io.BytesIO(payload),
                    filename=filename,
                    caption=caption if sent == 0 else None,
                )
            sent += 1
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            logger.warning(
                "MCP image normalization failed index=%s mime=%s bytes=%s error=%s",
                index, mime_type, len(data), exc,
            )
            try:
                await update.message.reply_document(
                    document=io.BytesIO(data),
                    filename=f"cloudflare_image_{index}.bin",
                    caption=caption if sent == 0 else None,
                )
                sent += 1
            except Exception:
                logger.exception("MCP image delivery failed index=%s", index)

    return sent
