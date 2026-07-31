import re
import logging
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)


DRIVE_KEYWORDS = [
    "drive", "folder", "map", "list", "files",
    "insta", "picture", "pdf", "audio", "other", "tosspage",
]


async def send_long_text(update: Update, text: str):
    if not text:
        await update.message.reply_text("Kuch nahi mila.")
        return
    for i in range(0, len(text), 4000):
        await update.message.reply_text(text[i:i + 4000])


async def send_download(update: Update, drive, sandbox, serial: int):
    await update.message.reply_text(f"{serial} download ho raha hai ⏬...")

    status, msg = drive.download_by_serial(serial, sandbox)
    if status != "ok":
        await update.message.reply_text(msg)
        return

    path = sandbox.path_for(msg)
    if not path.exists():
        await update.message.reply_text("File local pe nahi mili.")
        return

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > 48:
        await update.message.reply_text(
            f"File bahut badi hai ({size_mb:.1f} MB).\nTelegram limit \~50MB hai."
        )
        return

    await update.message.reply_text(f"Bhej raha hu... ({size_mb:.1f} MB) 📤")

    name_lower = msg.lower()
    is_video = name_lower.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))
    is_photo = name_lower.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"))
    is_audio = name_lower.endswith((".mp3", ".ogg", ".m4a", ".wav", ".aac"))

    try:
        with open(path, "rb") as f:
            if is_video:
                # Video → Telegram mein playable preview + player
                await update.message.reply_video(
                    video=f,
                    filename=msg,
                    supports_streaming=True,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )
            elif is_photo:
                await update.message.reply_photo(
                    photo=f,
                    filename=msg,
                    read_timeout=90,
                    write_timeout=90,
                    connect_timeout=30,
                )
            elif is_audio:
                await update.message.reply_audio(
                    audio=f,
                    filename=msg,
                    read_timeout=90,
                    write_timeout=90,
                    connect_timeout=30,
                )
            else:
                await update.message.reply_document(
                    document=f,
                    filename=msg,
                    read_timeout=120,
                    write_timeout=120,
                    connect_timeout=60,
                )

    except Exception as e:
        error = str(e)
        logger.exception("send_download failed")
        if "Timed out" in error or "timeout" in error.lower():
            await update.message.reply_text(
                f"File save ho gayi lekin bhejne mein timeout aa gaya.\n"
                f"Size: {size_mb:.1f} MB\n"
                f"Thodi der baad dubara try karo."
            )
        else:
            await update.message.reply_text(f"Bhej nahi paya: {error[:150]}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive = context.application.bot_data["drive"]
    sandbox = context.application.bot_data["sandbox"]
    agent = context.application.bot_data["agent"]
    memory = context.application.bot_data["memory"]

    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Kuch toh bol yaar 😏")
        return

    history = memory.get(uid)
    low = text.lower()

    # Download by number
    m = re.search(r"(?:download\s+(\d+)|(\d+)\s*download)", low)
    if m:
        await send_download(update, drive, sandbox, int(m.group(1) or m.group(2)))
        return

    # Drive keywords
    if any(k in low for k in DRIVE_KEYWORDS):
        sub = "root"
        for folder in ["insta", "picture", "pdf", "audio", "other", "tosspage"]:
            if folder in low:
                sub = folder
                break
        if "map" in low and sub == "root":
            sub = "map"
        await send_long_text(update, drive.list_files(sub))
        return

    # Normal AI chat
    try:
        result = await agent.ainvoke({"input": text, "chat_history": history})
        reply = result.get("output") or "Kuch samajh nahi aaya."
        history.append(HumanMessage(content=text))
        history.append(AIMessage(content=reply))
        memory.save(uid, history)
        await send_long_text(update, reply)
    except Exception as e:
        logger.exception("handle_text failed")
        await update.message.reply_text(
            f"Error 😤\nTry: Map folder list karo\nya /drive\n{str(e)[:120]}"
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = context.application.bot_data["memory"]
    memory.clear(update.effective_user.id)
    await update.message.reply_text(
        "Hlo baby 😈\n\n"
        "• Map folder list karo\n"
        "• Picture folder dikhao\n"
        "• 3 download karo\n\n"
        "/drive   /list Insta   /download 2"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = context.application.bot_data["memory"]
    memory.clear(update.effective_user.id)
    await update.message.reply_text("Memory saaf 🔥")
