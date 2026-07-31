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
    try:
        with open(path, "rb") as f:
            await update.message.reply_document(document=f, filename=msg)
    except Exception as e:
        await update.message.reply_text(f"File save hui lekin bhej nahi paya: {e}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive = context.application.bot_data["drive"]
    sandbox = context.application.bot_data["sandbox"]
    agent = context.application.bot_data["agent"]
    memory = context.application.bot_data["memory"]   # ← NEW

    uid = update.effective_user.id
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Kuch toh bol yaar 😏")
        return

    history = memory.get(uid)   # ← dict se SQLite
    low = text.lower()

    m = re.search(r"(?:download\s+(\d+)|(\d+)\s*download)", low)
    if m:
        await send_download(update, drive, sandbox, int(m.group(1) or m.group(2)))
        return

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

    try:
        result = await agent.ainvoke({"input": text, "chat_history": history})
        reply = result.get("output") or "Kuch samajh nahi aaya."
        history.append(HumanMessage(content=text))
        history.append(AIMessage(content=reply))
        memory.save(uid, history)   # ← dict update ki jagah
        await send_long_text(update, reply)
    except Exception as e:
        logger.exception("handle_text failed")
        await update.message.reply_text(
            f"Error 😤\nTry: Map folder list karo\nya /drive\n{str(e)[:120]}"
        )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = context.application.bot_data["memory"]
    memory.clear(update.effective_user.id)   # ← NEW
    await update.message.reply_text(
        "Hlo baby 😈\n\n"
        "• Map folder list karo\n"
        "• Picture folder dikhao\n"
        "• 3 download karo\n\n"
        "/drive   /list Insta   /download 2"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = context.application.bot_data["memory"]
    memory.clear(update.effective_user.id)   # ← NEW
    await update.message.reply_text("Memory saaf 🔥")
