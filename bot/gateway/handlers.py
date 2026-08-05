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
from bot.infra.tts import generate_voice_note

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
    
    welcome_text = (
        "Hlo 😈\n\n"
        "Main update ho gayi hoon! Ab mere paas:\n"
        "🕒 **Time Awareness:** Main waqt ke hisaab se react karungi.\n"
        "🎙 **Voice Notes:** Kisi bhi reply ke baad `/voice` likho, main bol kar sunaungi.\n"
        "👁 **Enhanced Vision:** Photos par mere reactions ab aur bhi personal honge.\n"
        "🎭 **Dynamic Moods:** `/mood` se mera vibe change karo.\n\n"
        "Batao, aaj raat kya plan hai? 😏"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")


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
        await update.message.reply_text("Abhi files nahi khol pa rahi.")
        return
    text = drive.list_files(update.effective_user.id, "root")
    await send_long_text(update, text)


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    drive = _get_drive(context)
    if not drive:
        await update.message.reply_text("Abhi files nahi khol pa rahi.")
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
        await update.message.reply_text("Abhi files nahi khol pa rahi.")
        return
    await send_long_text(update, drive.search(" ".join(context.args)))


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    sandbox = context.application.bot_data["sandbox"]
    drive = _get_drive(context)
    if not drive:
        await update.message.reply_text("Abhi files nahi khol pa rahi.")
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
        await update.message.reply_text("Abhi files nahi khol pa rahi.")
        return
    sandbox = context.application.bot_data["sandbox"]
    uid = update.effective_user.id
    await update.message.reply_text("ruki…")
    status, msg = drive.download_by_serial(
        uid, serial, sandbox.root, subfolder=subfolder
    )
    if status != "ok":
        await update.message.reply_text(msg)
        return
    await _send_media_with_followup(update, context, msg, uid)


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generate a voice note of the last bot reply or custom text."""
    if not _allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    history = memory.get_history(uid)
    
    text = " ".join(context.args) if context.args else ""
    if not text:
        # Get last AI message
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
        await update.message.reply_voice(voice=open(path, 'rb'))
        os.remove(path)
    else:
        await update.message.reply_text("Abhi gala kharab hai, baad mein try karna.")

# ───────────── vault handlers ─────────────

async def cmd_vault_setcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /vault_setcode <code>\nExample: /vault_setcode 1234")
        return
    code = context.args[0]
    memory = context.application.bot_data["memory"]
    memory.set_vault_code(update.effective_user.id, code)
    await update.message.reply_text(f"✅ Secret code set ho gaya hai. Ab aap apni private memories vault mein save kar sakte hain. 🤫")

async def cmd_vault_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    last_media = memory.get_last_media(uid)
    
    if not last_media:
        await update.message.reply_text("Abhi koi media nahi mili jo main vault mein daal sakun. Pehle kuch bhej toh sahi... 😏")
        return
    
    label = " ".join(context.args) if context.args else "Secret"
    memory.add_vault_entry(uid, last_media["file_key"], last_media["name"], label, last_media["description"])
    await update.message.reply_text(f"🔒 Yeh memory ('{label}') ab hamare secret vault mein safe hai. Sirf hamare liye... 😈")

async def cmd_vault_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    saved_code = memory.get_vault_code(uid)
    
    if not saved_code:
        await update.message.reply_text("Pehle /vault_setcode se ek code set karo.")
        return
    
    if not context.args or context.args[0] != saved_code:
        await update.message.reply_text("❌ Galat code! Vault kholne ke liye sahi code chahiye... try again. 😏")
        return
    
    entries = memory.get_vault_entries(uid)
    if not entries:
        await update.message.reply_text("Vault abhi khali hai. Kuch 'khas' add karo na... 😈")
        return
    
    text = "🔒 **Hamari Secret Memories:**\n\n"
    for e in entries:
        text += f"ID: `{e['id']}` | Label: **{e['label']}** | {e['file_name']}\n"
    
    text += "\nKholne ke liye: `/vault_open <id> <code>`"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_vault_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /vault_open <id> <code>")
        return
    
    entry_id = int(context.args[0])
    code = context.args[1]
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    
    saved_code = memory.get_vault_code(uid)
    if code != saved_code:
        await update.message.reply_text("❌ Galat code! Tumhe lagta hai main itni asani se dikha dungi? 😏")
        return
    
    entries = memory.get_vault_entries(uid)
    target = next((e for e in entries if e["id"] == entry_id), None)
    
    if not target:
        await update.message.reply_text("Yeh ID toh nahi mili.")
        return
    
    await update.message.reply_text("Ruko, vault se nikal rahi hoon... 🤫")
    # In this implementation, file_id is stored in file_key field of vault_entries
    try:
        # Check if it's a file_id or local path. 
        # The existing system uses file_key as local filename for media_memory.
        # But for vault, we might want to store Telegram file_id.
        # Let's assume for now it's a file_id if it looks like one.
        await update.message.reply_document(document=target["file_id"], caption=f"Hamari memory: {target['label']}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def cmd_vault_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /vault_del <id> <code>")
        return
    
    entry_id = int(context.args[0])
    code = context.args[1]
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    
    saved_code = memory.get_vault_code(uid)
    if code != saved_code:
        await update.message.reply_text("❌ Galat code!")
        return
    
    memory.delete_vault_entry(uid, entry_id)
    await update.message.reply_text(f"✅ Memory ID {entry_id} delete ho gayi. Ab wo sirf hamare dimaag mein rahegi... 😈")

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
            await update.message.reply_text("Abhi files nahi khol pa rahi.")
            return
        sandbox = context.application.bot_data["sandbox"]
        kind = getattr(parsed, "media_kind", "any") or "any"
        label = {"image": "photo", "video": "video"}.get(kind, "file")
        await update.message.reply_text("ek sec…")
        status, msg = drive.download_random(
            uid, parsed.subfolder or "root", sandbox.root, media_kind=kind
        )
        if status != "ok":
            await update.message.reply_text(msg)
            return
        await _send_media_with_followup(update, context, msg, uid)
        return

    if parsed.intent == Intent.DRIVE_LIST:
        if not drive:
            await update.message.reply_text("Abhi files nahi khol pa rahi.")
            return
        await send_long_text(update, drive.list_files(uid, parsed.subfolder))
        return

    if parsed.intent == Intent.DRIVE_SEARCH:
        if not drive:
            await update.message.reply_text("Abhi files nahi khol pa rahi.")
            return
        await send_long_text(update, drive.search(parsed.search_query or text))
        return

    if parsed.intent == Intent.VOICE:
        await cmd_voice(update, context)
        return

    if parsed.intent == Intent.VAULT_ADD:
        await cmd_vault_add(update, context)
        return

    if parsed.intent == Intent.VAULT_LIST:
        # For natural language, we need to handle the code. 
        # If not provided, we ask or check if a session code exists.
        await cmd_vault_list(update, context)
        return

    if parsed.intent == Intent.VAULT_OPEN:
        await cmd_vault_open(update, context)
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
        time_context=ctx["time_context"],
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
            "Abhi nahi ho paya, thodi der baad try karo."
        )


async def _transcribe_and_reply(update, context, file_bytes: bytes, filename: str, label: str):
    """Shared path: show status → whisper → save memory → reply (chunked)."""
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    uid = update.effective_user.id

    if not groq_key:
        await update.message.reply_text("Abhi sun nahi pa rahi.")
        return

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
        # Natural reply on what was said (no command brochure)
        try:
            llm = context.application.bot_data["llm"]
            tools = context.application.bot_data["tools"]
            ctx = build_context_packet(memory, uid, user_text=preview)
            chain = build_chat_agent(
                llm,
                tools,
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
            logger.exception("post-transcript chat failed")
            await send_long_text(update, transcript)
    except Exception as e:
        logger.exception("transcribe failed")
        try:
            await status.edit_text("Abhi sun nahi pa rahi, thodi der baad try karo.")
        except Exception:
            await update.message.reply_text("Abhi sun nahi pa rahi, thodi der baad try karo.")


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
        await _ask_enhance_mode(update, context, name)
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
            await query.edit_message_text("Abhi files nahi khol pa rahi.")
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


# ─────────────────────────────────────────────────────────────────────────────
# IMAGE ENHANCEMENT HANDLERS
# ─────────────────────────────────────────────────────────────────────────────
from bot.infra.image_enhance import enhance_image, EnhanceMode

ENHANCE_ACTIONS = [
    ("🎨 AI Enhance (FREE)", "enhance_regen"),
    ("❌ Skip", "enhance_skip"),
]


async def _ask_enhance_mode(update: Update, context: ContextTypes.DEFAULT_TYPE, local_name: str):
    context.user_data["enhance_file"] = local_name
    keyboard = [[InlineKeyboardButton(t, callback_data=d)] for t, d in ENHANCE_ACTIONS]
    await update.message.reply_text(
        "Photo mili. Enhance karein?",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def enhance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed(query.from_user.id):
        return

    action = query.data
    if action == "enhance_skip":
        context.user_data.pop("enhance_file", None)
        await query.edit_message_text("Skip ✅")
        return

    local_name = context.user_data.get("enhance_file")
    if not local_name:
        await query.edit_message_text("Koi pending photo nahi.")
        return

    sandbox = context.application.bot_data["sandbox"]
    path = sandbox.path_for(local_name)
    if not path.exists():
        await query.edit_message_text("File missing — dubara bhejo.")
        context.user_data.pop("enhance_file", None)
        return

    mode_map = {
        "enhance_regen":   EnhanceMode.REGENERATE,
        "enhance_upscale": EnhanceMode.UPSCALE,
        "enhance_full":    EnhanceMode.FULL,
    }
    mode = mode_map.get(action, EnhanceMode.FULL)

    mode_labels = {
        EnhanceMode.REGENERATE: "🎨 AI Regeneration",
        EnhanceMode.UPSCALE:    "📐 Free Upscale",
        EnhanceMode.FULL:       "🔥 Full (FREE)",
    }
    await query.edit_message_text(
        f"{mode_labels[mode]} shuru ho raha hai… ⏳\n_(30–90 seconds lagenge)_",
        parse_mode="Markdown",
    )

    try:
        image_bytes = path.read_bytes()
        enhanced_bytes, description = await enhance_image(
            image_bytes, mode=mode, scale=4, strength=0.55,
        )

        uid = query.from_user.id
        memory = context.application.bot_data["memory"]
        output_name = f"enhanced_{local_name}"
        output_path = sandbox.path_for(output_name)
        output_path.write_bytes(enhanced_bytes)

        memory.add_media(uid, file_key=output_name, name=output_name,
                         type_="image", description=description)

        await context.bot.send_photo(
            chat_id=query.message.chat_id,
            photo=enhanced_bytes,
            caption=f"✅ {description}",
        )

        h = memory.get_history(uid)
        h.append(AIMessage(content=f"[Enhanced image bheji: {mode.value}]\n{description}"))
        memory.save_history(uid, h, config.MAX_HISTORY_MESSAGES)

        context.user_data.pop("enhance_file", None)
        path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)

    except Exception as e:
        logger.exception("enhance failed")
        try:
            await query.edit_message_text(f"Enhancement fail 😤\n{str(e)[:250]}")
        except Exception:
            await context.bot.send_message(query.message.chat_id, f"Enhancement fail 😤\n{str(e)[:250]}")


async def cmd_enhance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/enhance — last photo ko enhance karo"""
    if not _allowed(update.effective_user.id):
        return
    pending = context.user_data.get("enhance_file")
    if not pending:
        await update.message.reply_text(
            "Pehle ek photo bhejo, phir /enhance use karo. 📸"
        )
        return
    await _ask_enhance_mode(update, context, pending)
