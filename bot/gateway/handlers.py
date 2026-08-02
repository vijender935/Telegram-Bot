import io
import logging
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage, AIMessage

from bot import config
from bot.domain.intent import Intent, parse_intent
from bot.domain.mood import MOODS, MOOD_MAP
from bot.domain.learning import profile_to_prompt_text, should_extract, extract_and_merge, empty_profile
from bot.domain.orchestrator import build_context_packet, maybe_update_session_summary, media_followup_lines
from bot.agent.chat_agent import build_chat_agent
from bot.gateway.formatters import send_long_text, send_local_file
from bot.infra.transcribe import transcribe_audio, extract_audio_from_video
from bot.infra.media_describe import describe_media_path, is_image, is_video

logger = logging.getLogger(__name__)


def _allowed(uid: int) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    return uid in config.ALLOWED_USER_IDS


def _get_drive(context):
    """Drive client return karo. None agar credentials missing hain."""
    return context.application.bot_data.get("drive")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_history(update.effective_user.id)
    await update.message.reply_text(
        "Hlo baby 😈\n\n"
        "Normal baat karo — main mood mein reply dungi.\n"
        "Voice / audio / video bhejo → transcript.\n"
        "Map folder list karo / 3 download karo.\n"
        "Vibe change: /mood"
    )


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_history(update.effective_user.id)
    await update.message.reply_text("Chat history saaf 🔥 (profile same rahega — /forgetprofile se profile bhi)")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    profile = memory.get_profile(update.effective_user.id)
    text = profile_to_prompt_text(profile)
    await update.message.reply_text(
        "🧠 Jo maine tere baare mein seekha:\n\n" + text +
        "\n\n/forgetprofile — yeh bhool jaaun"
    )


async def cmd_forgetprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_profile(update.effective_user.id)
    await update.message.reply_text("Profile bhool gayi. Naye sir se seekhungi 🔥")


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
    drive = _get_drive(context)
    if not drive:
        await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
        return
    text = drive.list_files(update.effective_user.id, "root")
    await send_long_text(update, text)


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    drive = _get_drive(context)
    if not drive:
        await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
        return
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
    drive = _get_drive(context)
    if not drive:
        await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
        return
    await send_long_text(update, drive.search(" ".join(context.args)))


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    sandbox = context.application.bot_data["sandbox"]
    drive = _get_drive(context)
    if not drive:
        await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
        return
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


async def _describe_and_remember(context, uid: int, local_name: str) -> str:
    """Vision describe + save media memory. Returns description or empty."""
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
        memory.add_media(uid, file_key=local_name, name=local_name, type_=type_, description=desc)
        return desc
    except Exception:
        logger.exception("media describe failed")
        return ""


async def _send_media_with_followup(update, context, local_name: str, uid: int):
    sandbox = context.application.bot_data["sandbox"]
    memory = context.application.bot_data["memory"]
    path = sandbox.path_for(local_name)
    # describe BEFORE send_local_file deletes the file
    desc = await _describe_and_remember(context, uid, local_name)
    await send_local_file(update, path)
    if config.MEDIA_FOLLOWUP and desc:
        mood = memory.get_mood(uid)
        follow = media_followup_lines(desc, mood)
        await send_long_text(update, follow)
        # inject into history so chat knows she "sent" it
        from langchain_core.messages import HumanMessage, AIMessage
        h = memory.get_history(uid)
        h.append(AIMessage(content=f"[maine yeh media bheji: {local_name}]\n{desc}\n\n{follow}"))
        memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)


async def _do_download(update: Update, context: ContextTypes.DEFAULT_TYPE, serial: int, subfolder: str = "root"):
    drive = _get_drive(context)
    if not drive:
        await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
        return
    sandbox = context.application.bot_data["sandbox"]
    uid = update.effective_user.id
    await update.message.reply_text(f"⬇️ ruki… #{serial} bhejti hoon")
    status, msg = drive.download_by_serial(
        uid, serial, sandbox.root, subfolder=subfolder
    )
    if status != "ok":
        await update.message.reply_text(msg)
        return
    await _send_media_with_followup(update, context, msg, uid)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not _allowed(uid):
        return

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text("Kuch toh bol yaar 😏")
        return

    drive = _get_drive(context)
    memory = context.application.bot_data["memory"]
    llm = context.application.bot_data["llm"]
    tools = context.application.bot_data["tools"]

    parsed = parse_intent(text)

    if parsed.intent == Intent.DRIVE_DOWNLOAD and parsed.serial is not None:
        await _do_download(update, context, parsed.serial, subfolder=parsed.subfolder or "root")
        return

    if parsed.intent == Intent.DRIVE_RANDOM:
        if not drive:
            await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
            return
        sandbox = context.application.bot_data["sandbox"]
        await update.message.reply_text("🎲 ek random choose karti hoon…")
        status, msg = drive.download_random(uid, parsed.subfolder or "root", sandbox.root)
        if status != "ok":
            await update.message.reply_text(msg)
            return
        await _send_media_with_followup(update, context, msg, uid)
        return

    if parsed.intent == Intent.DRIVE_LIST:
        if not drive:
            await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
            return
        await send_long_text(update, drive.list_files(uid, parsed.subfolder))
        return

    if parsed.intent == Intent.DRIVE_SEARCH:
        if not drive:
            await update.message.reply_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
            return
        await send_long_text(update, drive.search(parsed.search_query or text))
        return

    # CHAT — rich context packet (mood, profile, media, session, emotion)
    history = memory.get_history(uid)
    ctx = build_context_packet(memory, uid, user_text=text)
    chain = build_chat_agent(
        llm,
        tools,
        current_mood=ctx["mood"],
        user_profile=ctx["profile"],
        session_summary=ctx["session_summary_text"],
        last_media=ctx["last_media_text"],
        active_fantasy=ctx["fantasy_text"],
        emotion=ctx["emotion"],
    )

    try:
        reply = await chain.ainvoke({"input": text, "chat_history": history})
        if not reply or not str(reply).strip():
            reply = "Hmm... bol na, sun rahi hoon 😏"
        history.append(HumanMessage(content=text))
        history.append(AIMessage(content=reply))
        memory.save_history(uid, history, config.MAX_HISTORY_MESSAGES)
        await send_long_text(update, reply)

        if should_extract(text):
            try:
                updated = await extract_and_merge(llm, ctx["profile"] or empty_profile(), text, reply)
                memory.set_profile(uid, updated)
                # ongoing fantasy field
                if updated.get("ongoing_fantasy"):
                    memory.set_fantasy(uid, updated["ongoing_fantasy"])
                logger.info("profile updated for user %s", uid)
            except Exception:
                logger.exception("learning update failed")

        try:
            await maybe_update_session_summary(llm, memory, uid, text, reply)
        except Exception:
            logger.exception("session summary side-effect failed")
    except Exception as e:
        logger.exception("chat failed")
        await update.message.reply_text(
            f"Error 😤\nTry /drive\n{str(e)[:120]}"
        )


async def _transcribe_and_reply(update, context, file_bytes: bytes, filename: str, label: str):
    """Shared path: show status → whisper → save memory → reply (chunked)."""
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    uid = update.effective_user.id

    if not groq_key:
        await update.message.reply_text("GROQ_API_KEY missing — transcript nahi ho sakta.")
        return

    status = await update.message.reply_text(f"🎧 {label} sun rahi hoon, transcript bana rahi hoon…")
    try:
        transcript = await transcribe_audio(file_bytes, filename, groq_key)
        # History mein pure transcript mat daalo — bohot lamba ho sakta hai
        preview = transcript if len(transcript) <= 1500 else transcript[:1500] + "…"
        h = memory.get_history(uid)
        h.append(HumanMessage(content=f"[{label}]\nTranscript: {preview}"))
        memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
        try:
            await status.edit_text("📝 Transcript ready:")
        except Exception:
            pass
        await send_long_text(update, transcript)
    except Exception as e:
        logger.exception("transcribe failed")
        err = str(e)
        # Telegram Message_too_long kabhi exception message mein aata hai
        if "Message_too_long" in err or "too long" in err.lower():
            await status.edit_text("Transcript bahut lamba tha — chunks mein bhej rahi hoon…")
            # last successful path unlikely; just report
            await update.message.reply_text(
                "Transcript fail: message limit. Chhota audio try karo ya dubara bhejo."
            )
        else:
            try:
                await status.edit_text(f"Transcript fail 😤\n{err[:250]}")
            except Exception:
                await update.message.reply_text(f"Transcript fail 😤\n{err[:250]}")


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
            # FIX: data already in buf — write directly, no double download
            sandbox.write_bytes(name, data)
            h = memory.get_history(uid)
            h.append(HumanMessage(content=f"[document: {name}]"))
            memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
            await _ask_file_method(update, context, name, "document")
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
        memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)
        await _ask_file_method(update, context, name, "photo")
    except Exception:
        logger.exception("photo failed")
        await update.message.reply_text("Photo fail.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telegram voice note (mic button) — usually .ogg"""
    if not _allowed(update.effective_user.id):
        return
    voice = update.message.voice
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        await _transcribe_and_reply(
            update, context, buf.getvalue(), "voice.ogg", "voice note"
        )
    except Exception:
        logger.exception("voice failed")
        await update.message.reply_text("Voice fail.")


async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Music / audio file sent as Telegram audio."""
    if not _allowed(update.effective_user.id):
        return
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
    """Video message (not document)."""
    if not _allowed(update.effective_user.id):
        return
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
    """Round video note."""
    if not _allowed(update.effective_user.id):
        return
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



# ---- incoming file: ask method (like /mood) ----
FILE_ACTIONS = [
    ("📝 Transcribe", "fileact_transcribe"),
    ("💾 Save local", "fileact_save"),
    ("☁️ Upload Drive", "fileact_upload"),
    ("❌ Skip", "fileact_skip"),
]


async def _ask_file_method(update: Update, context: ContextTypes.DEFAULT_TYPE, local_name: str, kind: str):
    context.user_data["pending_file"] = {"name": local_name, "kind": kind}
    keyboard = [[InlineKeyboardButton(t, callback_data=d)] for t, d in FILE_ACTIONS]
    await update.message.reply_text(
        f"File mili: `{local_name}`\nKya karoon?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def file_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed(query.from_user.id):
        return
    pending = context.user_data.get("pending_file")
    if not pending:
        await query.edit_message_text("Koi pending file nahi.")
        return

    name = pending["name"]
    sandbox = context.application.bot_data["sandbox"]
    drive = _get_drive(context)
    path = sandbox.path_for(name)
    action = query.data

    if action == "fileact_skip":
        path.unlink(missing_ok=True)
        context.user_data.pop("pending_file", None)
        await query.edit_message_text("Skip 👍")
        return

    if action == "fileact_save":
        context.user_data.pop("pending_file", None)
        await query.edit_message_text(f"Saved local: `{name}`", parse_mode="Markdown")
        return

    if action == "fileact_upload":
        if not drive:
            await query.edit_message_text("⚠️ Drive connect nahi hai — GOOGLE credentials check karo.")
            return
        if not path.exists():
            await query.edit_message_text("File missing.")
            return
        try:
            up = drive.upload(path)
            context.user_data.pop("pending_file", None)
            await query.edit_message_text(f"☁️ Drive pe: {up}")
        except Exception as e:
            await query.edit_message_text(f"Upload fail: {e}")
        return

    if action == "fileact_transcribe":
        groq_key = context.application.bot_data.get("groq_api_key")
        if not groq_key or not path.exists():
            await query.edit_message_text("Transcribe nahi ho sakta (key/file).")
            return
        await query.edit_message_text("🎧 Transcript bana rahi hoon…")
        try:
            data = path.read_bytes()
            low = name.lower()
            if low.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v")):
                from bot.infra.transcribe import extract_audio_from_video
                data = extract_audio_from_video(data)
                fname = "audio.mp3"
            else:
                fname = name
            transcript = await transcribe_audio(data, fname, groq_key)
            memory = context.application.bot_data["memory"]
            h = memory.get_history(query.from_user.id)
            preview = transcript if len(transcript) <= 1500 else transcript[:1500] + "…"
            h.append(HumanMessage(content=f"[file:{name}]\nTranscript: {preview}"))
            memory.save_history(query.from_user.id, h, config.MAX_HISTORY_MESSAGES)
            context.user_data.pop("pending_file", None)
            await query.edit_message_text("📝 Transcript ready:")
            chat_id = query.message.chat_id
            chunk = transcript
            for j in range(0, len(chunk), 4000):
                await context.bot.send_message(chat_id, chunk[j:j + 4000])
        except Exception as e:
            logger.exception("fileact transcribe")
            await query.edit_message_text(f"Fail: {str(e)[:200]}")
