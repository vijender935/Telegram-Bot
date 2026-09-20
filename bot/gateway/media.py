import logging
import io
import os
from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage

from bot import config
from bot.gateway.formatters import send_long_text, send_local_file
from bot.infra.transcribe import transcribe_audio
from bot.infra.media_describe import describe_media_path, is_image, is_video
from bot.infra.tts import generate_voice_note
from bot.domain.orchestrator import build_context_packet, media_followup_lines
from bot.agent.chat_agent import build_chat_agent
from bot.agent.tools import build_tools

logger = logging.getLogger(__name__)

async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    history = memory.get_history(uid)
    text = " ".join(context.args) if context.args else ""
    if not text:
        for msg in reversed(history):
            if isinstance(msg, AIMessage):
                text = msg.content
                break
    if not text:
        await update.message.reply_text("Pehle kuch baat toh karo, tabhi toh bolungi 😏")
        return
    await update.message.reply_text("Ek sec, voice note bhej rahi hoon...")
    sandbox = context.application.bot_data["sandbox"]
    filename = f"voice_{uid}.mp3"
    path = sandbox.path_for(filename)
    if generate_voice_note(text, path):
        try:
            with open(path, 'rb') as f:
                await update.message.reply_voice(voice=f)
        finally:
            if os.path.exists(path):
                os.remove(path)
    else:
        await update.message.reply_text("Abhi gala kharab hai, baad mein try karna.")

# --- Media Handlers ---

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sandbox = context.application.bot_data["sandbox"]
    memory = context.application.bot_data["memory"]
    uid = update.effective_user.id
    photo = update.message.photo[-1]
    try:
        f = await context.bot.get_file(photo.file_id)
        name = f"photo_{uid}_{photo.file_unique_id}.jpg"
        path = sandbox.path_for(name)
        await f.download_to_drive(str(path))
        h = memory.get_history(uid)
        h.append(HumanMessage(content="[photo]"))
        memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
        desc = await _describe_and_remember(context, uid, name, file_id=photo.file_id)
        if desc:
            mood = memory.get_mood(uid)
            follow = media_followup_lines(desc, mood)
            await update.message.reply_text(follow)
            h.append(AIMessage(content=follow))
            memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
        await _ask_enhance_mode(update, context, name)
    except Exception:
        logger.exception("photo failed")
        await update.message.reply_text("Photo fail.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    sandbox = context.application.bot_data["sandbox"]
    uid = update.effective_user.id
    doc = update.message.document
    name = doc.file_name or f"doc_{doc.file_id}"
    low = name.lower()
    is_audio = low.endswith((".mp3", ".ogg", ".oga", ".m4a", ".wav", ".aac", ".flac", ".webm"))
    is_video = low.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        data = buf.getvalue()
        if is_audio and groq_key:
            await _transcribe_and_reply(update, context, data, name, f"audio: {name}")
        elif is_video and groq_key:
            status = await update.message.reply_text("🎬 Video se audio nikaal rahi hoon…")
            try:
                from bot.infra.transcribe import extract_audio_from_video
                audio = extract_audio_from_video(data)
                await status.delete()
                await _transcribe_and_reply(update, context, audio, "audio.mp3", f"video: {name}")
            except Exception as e:
                logger.exception("video transcript failed")
                await status.edit_text(f"Video transcript fail:\n{str(e)[:250]}")
        else:
            sandbox.write_bytes(name, data)
            h = memory.get_history(uid)
            h.append(HumanMessage(content=f"[document: {name}]"))
            memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
            await update.message.reply_text("File mil gayi. Batao normal language mein kya karna hai.")
    except Exception:
        logger.exception("document failed")
        await update.message.reply_text("Document fail.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        await _transcribe_and_reply(update, context, buf.getvalue(), "voice.ogg", "voice note")
    except Exception:
        logger.exception("voice failed")
        await update.message.reply_text("Voice fail.")

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    audio = update.message.audio
    name = audio.file_name or f"audio_{audio.file_unique_id}.mp3"
    try:
        tg_file = await context.bot.get_file(audio.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        await _transcribe_and_reply(update, context, buf.getvalue(), name, f"audio: {name}")
    except Exception:
        logger.exception("audio failed")
        await update.message.reply_text("Audio fail.")

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    video = update.message.video
    name = video.file_name or f"video_{video.file_unique_id}.mp4"
    try:
        tg_file = await context.bot.get_file(video.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        status = await update.message.reply_text("🎬 Video se audio nikaal rahi hoon…")
        try:
            from bot.infra.transcribe import extract_audio_from_video
            audio = extract_audio_from_video(buf.getvalue())
            await status.delete()
            await _transcribe_and_reply(update, context, audio, "audio.mp3", f"video: {name}")
        except Exception as e:
            logger.exception("video failed")
            await status.edit_text(f"Video transcript fail:\n{str(e)[:250]}")
    except Exception:
        logger.exception("video download failed")
        await update.message.reply_text("Video fail.")

async def handle_video_note(update: Update, context: ContextTypes.DEFAULT_TYPE):
    note = update.message.video_note
    try:
        tg_file = await context.bot.get_file(note.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        status = await update.message.reply_text("🎬 Video note process ho raha hai…")
        try:
            from bot.infra.transcribe import extract_audio_from_video
            audio = extract_audio_from_video(buf.getvalue())
            await status.delete()
            await _transcribe_and_reply(update, context, audio, "audio.mp3", "video note")
        except Exception as e:
            logger.exception("video_note failed")
            await status.edit_text(f"Video note fail:\n{str(e)[:250]}")
    except Exception:
        logger.exception("video_note download failed")
        await update.message.reply_text("Video note fail.")

# --- Internal Helpers ---

async def _ask_enhance_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, local_name: str):
    """Keep enhancement prompt-driven; never render an action keyboard."""
    context.user_data["enhance_file"] = local_name
    await update.message.reply_text(
        "Photo mil gayi. Agar enhance karna hai to normal language mein bolo, "
        "jaise: 'is photo ko enhance karo'."
    )


async def _describe_and_remember(context, uid: int, local_name: str, file_id: str | None = None) -> str:
    if not config.MEDIA_DESCRIBE_ON_DOWNLOAD:
        return ""
    memory = context.application.bot_data["memory"]
    sandbox = context.application.bot_data["sandbox"]
    path = sandbox.path_for(local_name)
    if not path.exists():
        return ""
    if not (is_image(local_name) or is_video(local_name)):
        return ""
    try:
        type_, desc = await describe_media_path(path)
        memory.add_media(uid, file_key=local_name, name=local_name, type_=type_, description=desc, file_id=file_id)
        return desc
    except Exception:
        logger.exception("media describe failed")
        return ""

async def _send_media_with_followup(update: Update, context: ContextTypes.DEFAULT_TYPE, filename: str, uid: int):
    sandbox = context.application.bot_data["sandbox"]
    path = sandbox.path_for(filename)
    await send_local_file(update, path)

async def _transcribe_and_reply(update, context, file_bytes, filename, label):
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    uid = update.effective_user.id
    status = await update.message.reply_text("sun rahi hoon…")
    try:
        transcript = await transcribe_audio(file_bytes, filename, groq_key)
        preview = transcript if len(transcript) <= 1500 else transcript[:1500] + "…"
        h = memory.get_history(uid)
        h.append(HumanMessage(content=f"[{label}]\n{preview}"))
        memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
        try:
            await status.delete()
        except Exception:
            pass
        llm = context.application.bot_data["llm"]
        tools = build_tools(memory=memory, user_id=uid, sandbox_path=config.SANDBOX_PATH, mcp_tools=context.application.bot_data.get("mcp_tools", []))
        ctx = build_context_packet(memory, uid, user_text=preview)
        chain = build_chat_agent(
            llm, tools,
            current_mood=ctx["mood"],
            user_profile=ctx["profile"],
            session_summary=ctx["session_summary_text"],
            last_media=ctx["last_media_text"],
            active_fantasy=ctx["fantasy_text"],
            emotion=ctx["emotion"],
            time_context=ctx["time_context"],
        )
        reply = await chain.ainvoke({"input": preview, "chat_history": h[:-1]})
        if reply and str(reply).strip():
            h.append(AIMessage(content=reply))
            memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
            await send_long_text(update, reply)
        else:
            await send_long_text(update, transcript)
    except Exception:
        logger.exception("transcribe failed")
        await update.message.reply_text("Abhi sun nahi pa rahi.")
