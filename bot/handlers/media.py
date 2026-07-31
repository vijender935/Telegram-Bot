import logging
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sandbox = context.application.bot_data["sandbox"]
    memory = context.application.bot_data["memory"]
    uid = update.effective_user.id
    doc = update.message.document
    try:
        f = await context.bot.get_file(doc.file_id)
        name = doc.file_name or f"doc_{doc.file_id}"
        await f.download_to_drive(str(sandbox.path_for(name)))
        await update.message.reply_text(f"Save: `{name}`")
        history = memory.get(uid)
        history.append(HumanMessage(content=f"[document: {name}]"))
        memory.save(uid, history)
    except Exception:
        logger.exception("document failed")
        await update.message.reply_text("Document fail.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sandbox = context.application.bot_data["sandbox"]
    memory = context.application.bot_data["memory"]
    uid = update.effective_user.id
    photo = update.message.photo[-1]
    try:
        f = await context.bot.get_file(photo.file_id)
        name = f"photo_{uid}_{photo.file_unique_id}.jpg"
        await f.download_to_drive(str(sandbox.path_for(name)))
        await update.message.reply_text(f"Photo 😈 `{name}`")
        history = memory.get(uid)
        history.append(HumanMessage(content="[photo]"))
        memory.save(uid, history)
    except Exception:
        logger.exception("photo failed")
        await update.message.reply_text("Photo fail.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sandbox = context.application.bot_data["sandbox"]
    memory = context.application.bot_data["memory"]
    uid = update.effective_user.id
    voice = update.message.voice
    try:
        f = await context.bot.get_file(voice.file_id)
        name = f"voice_{uid}_{voice.file_unique_id}.ogg"
        await f.download_to_drive(str(sandbox.path_for(name)))
        await update.message.reply_text(f"Voice 🔥 `{name}`")
        history = memory.get(uid)
        history.append(HumanMessage(content="[voice]"))
        memory.save(uid, history)
    except Exception:
        logger.exception("voice failed")
        await update.message.reply_text("Voice fail.")