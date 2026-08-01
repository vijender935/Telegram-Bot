import io
import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage

from bot import config
from bot.domain.intent import Intent, parse_intent
from bot.domain.mood import MOODS, MOOD_MAP
from bot.agent.chat_agent import build_chat_agent
from bot.gateway.formatters import send_long_text, send_local_file
from bot.infra.transcribe import transcribe_audio, extract_audio_from_video

logger = logging.getLogger(__name__)


def _allowed(uid: int) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    return uid in config.ALLOWED_USER_IDS


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_history(update.effective_user.id)
    await update.message.reply_text(
        "Hlo baby 😈\n\n"
        "• Map folder list karo\n"
        "• Picture folder dikhao\n"
        "• 3 download karo\n"
        "• /mood se vibe change\n\n"
        "/drive  /list Insta  /download 2  /mood"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_history(update.effective_user.id)
    await update.message.reply_text("Memory saaf 🔥")


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    keyboard = [[InlineKeyboardButton(t, callback_data=d)] for t, d in MOODS]
    await update.message.reply_text(
        "🎭 Apna vibe choose karo:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def mood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed(query.from_user.id):
        return
    selected = MOOD_MAP.get(query.data)
    if not selected:
        await query.edit_message_text("Invalid mood.")
        return
    memory = context.application.bot_data["memory"]
    memory.set_mood(query.from_user.id, selected)
    await query.edit_message_text(
        f"✅ Vibe set → *{selected}*\n\nAb is mood mein baat karungi 😈",
        parse_mode="Markdown",
    )


async def cmd_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    drive = context.application.bot_data["drive"]
    text = drive.list_files(update.effective_user.id, "root")
    await send_long_text(update, text)


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    drive = context.application.bot_data["drive"]
    sub = " ".join(context.args) if context.args else "root"
    text = drive.list_files(update.effective_user.id, sub)
    await send_long_text(update, text)


async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /download <number>\nPehle /drive chalao.")
        return
    await _do_download(update, context, int(context.args[0]))


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /search <query>")
        return
    drive = context.application.bot_data["drive"]
    await send_long_text(update, drive.search(" ".join(context.args)))


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    sandbox = context.application.bot_data["sandbox"]
    drive = context.application.bot_data["drive"]
    if not context.args:
        await update.message.reply_text("Usage: /upload <local_filename>")
        return
    path = sandbox.path_for(context.args[0])
    if not path.exists():
        await update.message.reply_text(f"Local file nahi mili: {context.args[0]}")
        return
    try:
        name = drive.upload(path)
        await update.message.reply_text(f"Upload → {name}")
    except Exception as e:
        await update.message.reply_text(f"Upload fail: {e}")


async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    sandbox = context.application.bot_data["sandbox"]
    if not context.args:
        await update.message.reply_text("Usage: /delete <filename>")
        return
    try:
        sandbox.delete(context.args[0])
        await update.message.reply_text(f"Deleted: {context.args[0]}")
    except Exception as e:
        await update.message.reply_text(str(e))


async def _do_download(update: Update, context: ContextTypes.DEFAULT_TYPE, serial: int):
    drive = context.application.bot_data["drive"]
    sandbox = context.application.bot_data["sandbox"]
    status, msg = drive.download_by_serial(update.effective_user.id, serial, sandbox.root)
    if status != "ok":
        await update.message.reply_text(msg)
        return
    await send_local_file(update, sandbox.path_for(msg))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _allowed(uid):
        return

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Kuch toh bol yaar 😏")
        return

    drive = context.application.bot_data["drive"]
    memory = context.application.bot_data["memory"]
    llm = context.application.bot_data["llm"]
    tools = context.application.bot_data["tools"]

    parsed = parse_intent(text)

    if parsed.intent == Intent.DRIVE_DOWNLOAD and parsed.serial is not None:
        await _do_download(update, context, parsed.serial)
        return

    if parsed.intent == Intent.DRIVE_LIST:
        await send_long_text(update, drive.list_files(uid, parsed.subfolder))
        return

    if parsed.intent == Intent.DRIVE_SEARCH:
        await send_long_text(update, drive.search(parsed.search_query or text))
        return

    # CHAT only — no drive tools needed in agent for reliability
    history = memory.get_history(uid)
    mood = memory.get_mood(uid)
    agent = build_chat_agent(llm, tools, current_mood=mood)

    try:
        result = await agent.ainvoke({"input": text, "chat_history": history})
        reply = result.get("output") or "Kuch samajh nahi aaya."
        history.append(HumanMessage(content=text))
        history.append(AIMessage(content=reply))
        memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)
        await send_long_text(update, reply)
    except Exception as e:
        logger.exception("chat failed")
        await update.message.reply_text(
            f"Error 😤\nTry /drive\n{str(e)[:120]}"
        )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    sandbox = context.application.bot_data["sandbox"]
    uid = update.effective_user.id
    doc = update.message.document
    name = doc.file_name or f"doc_{doc.file_id}"
    low = name.lower()
    is_audio = low.endswith((".mp3", ".ogg", ".m4a", ".wav", ".aac"))
    is_video = low.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        data = buf.getvalue()

        if is_audio and groq_key:
            transcript = await transcribe_audio(data, name, groq_key)
            h = memory.get_history(uid)
            h.append(HumanMessage(content=f"[audio: {name}]\nTranscript: {transcript}"))
            memory.save_history(uid, h)
            await update.message.reply_text(f"📝 Transcript:\n\n{transcript}")
        elif is_video and groq_key:
            audio = extract_audio_from_video(data)
            transcript = await transcribe_audio(audio, "audio.mp3", groq_key)
            h = memory.get_history(uid)
            h.append(HumanMessage(content=f"[video: {name}]\nTranscript: {transcript}"))
            memory.save_history(uid, h)
            await update.message.reply_text(f"📝 Transcript:\n\n{transcript}")
        else:
            await tg_file.download_to_drive(str(sandbox.path_for(name)))
            h = memory.get_history(uid)
            h.append(HumanMessage(content=f"[document: {name}]"))
            memory.save_history(uid, h)
            await update.message.reply_text(f"Saved: `{name}`")
    except Exception:
        logger.exception("document failed")
        await update.message.reply_text("Document fail.")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    sandbox = context.application.bot_data["sandbox"]
    memory = context.application.bot_data["memory"]
    uid = update.effective_user.id
    photo = update.message.photo[-1]
    try:
        f = await context.bot.get_file(photo.file_id)
        name = f"photo_{uid}_{photo.file_unique_id}.jpg"
        await f.download_to_drive(str(sandbox.path_for(name)))
        h = memory.get_history(uid)
        h.append(HumanMessage(content="[photo]"))
        memory.save_history(uid, h)
        await update.message.reply_text(f"Photo 😈 `{name}`")
    except Exception:
        logger.exception("photo failed")
        await update.message.reply_text("Photo fail.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    uid = update.effective_user.id
    voice = update.message.voice
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        if groq_key:
            transcript = await transcribe_audio(buf.getvalue(), "voice.ogg", groq_key)
            h = memory.get_history(uid)
            h.append(HumanMessage(content=f"[voice]\nTranscript: {transcript}"))
            memory.save_history(uid, h)
            await update.message.reply_text(f"📝 Transcript:\n\n{transcript}")
        else:
            await update.message.reply_text("Groq key missing.")
    except Exception:
        logger.exception("voice failed")
        await update.message.reply_text("Voice fail.")
