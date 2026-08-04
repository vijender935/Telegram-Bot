import logging
from pathlib import Path

from telegram import Update

from bot import config

logger = logging.getLogger(__name__)


async def send_long_text(update: Update, text: str):
    if not text:
        await update.message.reply_text("Kuch nahi mila.")
        return
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i + 4000])


async def send_local_file(update: Update, path: Path):
    if not path.exists():
        await update.message.reply_text("File nahi mili.")
        return

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > config.MAX_SEND_MB:
        path.unlink(missing_ok=True)
        await update.message.reply_text("Yeh file bahut badi hai.")
        return

    name = path.name
    low = name.lower()
    is_video = low.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))
    is_photo = low.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))
    is_audio = low.endswith((".mp3", ".ogg", ".m4a", ".wav", ".aac"))

    try:
        with open(path, "rb") as f:
            if is_video:
                await update.message.reply_video(
                    video=f, filename=name, supports_streaming=True,
                    read_timeout=120, write_timeout=120, connect_timeout=60,
                )
            elif is_photo:
                await update.message.reply_photo(
                    photo=f, read_timeout=90, write_timeout=90, connect_timeout=30,
                )
            elif is_audio:
                await update.message.reply_audio(
                    audio=f, filename=name,
                    read_timeout=90, write_timeout=90, connect_timeout=30,
                )
            else:
                await update.message.reply_document(
                    document=f, filename=name,
                    read_timeout=120, write_timeout=120, connect_timeout=60,
                )
    except Exception as e:
        logger.exception("send_local_file failed")
        await update.message.reply_text("Abhi bhej nahi paayi, thodi der baad try karo.")
    finally:
        path.unlink(missing_ok=True)
