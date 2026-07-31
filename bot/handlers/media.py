import io
import logging
import subprocess
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes
from langchain_core.messages import HumanMessage

logger = logging.getLogger(__name__)


async def _transcribe(file_bytes: bytes, filename: str, groq_api_key: str) -> str:
    """Groq Whisper API se transcribe."""
    import httpx
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {groq_api_key}"},
            files={"file": (filename, file_bytes, "audio/mpeg")},
            data={"model": "whisper-large-v3-turbo", "response_format": "text"},
        )
        resp.raise_for_status()
        return resp.text.strip()


async def _extract_audio_bytes(video_bytes: bytes) -> bytes:
    """Video se audio extract (ffmpeg)."""
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as vf:
        vf.write(video_bytes)
        vf_path = vf.name
    out_path = vf_path.replace(".mp4", ".mp3")
    subprocess.run(
        ["ffmpeg", "-y", "-i", vf_path, "-vn", "-ar", "16000",
         "-ac", "1", "-b:a", "64k", out_path],
        capture_output=True, check=True,
    )
    Path(vf_path).unlink(missing_ok=True)
    audio = Path(out_path).read_bytes()
    Path(out_path).unlink(missing_ok=True)
    return audio


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    uid = update.effective_user.id
    doc = update.message.document
    name = doc.file_name or f"doc_{doc.file_id}"
    name_lower = name.lower()

    is_audio = name_lower.endswith((".mp3", ".ogg", ".m4a", ".wav", ".aac"))
    is_video = name_lower.endswith((".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"))

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        file_bytes = buf.getvalue()

        if is_audio and groq_key:
            transcript = await _transcribe(file_bytes, name, groq_key)
            history = memory.get(uid)
            history.append(HumanMessage(content=f"[audio: {name}]\nTranscript: {transcript}"))
            memory.save(uid, history)
            await update.message.reply_text(f"📝 Transcript:\n\n{transcript}")

        elif is_video and groq_key:
            audio_bytes = await _extract_audio_bytes(file_bytes)
            transcript = await _transcribe(audio_bytes, "audio.mp3", groq_key)
            history = memory.get(uid)
            history.append(HumanMessage(content=f"[video: {name}]\nTranscript: {transcript}"))
            memory.save(uid, history)
            await update.message.reply_text(f"📝 Transcript:\n\n{transcript}")

        else:
            sandbox = context.application.bot_data["sandbox"]
            await tg_file.download_to_drive(str(sandbox.path_for(name)))
            history = memory.get(uid)
            history.append(HumanMessage(content=f"[document: {name}]"))
            memory.save(uid, history)
            await update.message.reply_text(f"Saved: `{name}`")

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
        history = memory.get(uid)
        history.append(HumanMessage(content="[photo]"))
        memory.save(uid, history)
        await update.message.reply_text(f"Photo 😈 `{name}`")
    except Exception:
        logger.exception("photo failed")
        await update.message.reply_text("Photo fail.")


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    memory = context.application.bot_data["memory"]
    groq_key = context.application.bot_data.get("groq_api_key")
    uid = update.effective_user.id
    voice = update.message.voice
    try:
        tg_file = await context.bot.get_file(voice.file_id)
        buf = io.BytesIO()
        await tg_file.download_to_memory(buf)
        voice_bytes = buf.getvalue()

        if groq_key:
            transcript = await _transcribe(voice_bytes, "voice.ogg", groq_key)
            history = memory.get(uid)
            history.append(HumanMessage(content=f"[voice]\nTranscript: {transcript}"))
            memory.save(uid, history)
            await update.message.reply_text(f"📝 Transcript:\n\n{transcript}")
        else:
            await update.message.reply_text("Groq key missing.")

    except Exception:
        logger.exception("voice failed")
        await update.message.reply_text("Voice fail.")
