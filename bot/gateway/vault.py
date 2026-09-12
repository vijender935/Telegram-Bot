import logging
import time
from telegram import Update
from telegram.ext import ContextTypes
from bot import config
from bot.gateway.base import _allowed

logger = logging.getLogger(__name__)


def _guard(context):
    return context.application.bot_data.get("vault_guard")


async def _authenticate(update: Update, context: ContextTypes.DEFAULT_TYPE, code: str) -> bool:
    uid = update.effective_user.id
    guard = _guard(context)
    if guard:
        allowed, remaining = guard.can_attempt(uid)
        if not allowed:
            await update.message.reply_text(f"🔒 Vault temporarily locked. {remaining}s baad try karo.")
            return False
    memory = context.application.bot_data["memory"]
    if memory.verify_vault_code(uid, code):
        if guard:
            guard.success(uid)
        context.user_data["vault_unlocked_until"] = time.time() + config.VAULT_SESSION_SECONDS
        try:
            await update.message.delete()
        except Exception:
            pass
        return True
    if guard:
        remaining = guard.failure(uid)
        if remaining:
            await update.message.reply_text(f"❌ Wrong code. Vault {remaining}s ke liye lock ho gaya.")
        else:
            await update.message.reply_text("❌ Wrong vault code.")
    else:
        await update.message.reply_text("❌ Wrong vault code.")
    return False


def _session_unlocked(context) -> bool:
    return float(context.user_data.get("vault_unlocked_until", 0)) > time.time()


async def cmd_vault_setcode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /vault_setcode <code>")
        return
    code = context.args[0]
    if len(code) < 6:
        await update.message.reply_text("🔐 Code kam se kam 6 characters ka rakho.")
        return
    memory = context.application.bot_data["memory"]
    memory.set_vault_code(update.effective_user.id, code)
    try:
        await update.message.delete()
    except Exception:
        pass
    await update.message.reply_text("✅ Vault code set ho gaya.")


async def cmd_vault_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    file_id = None
    file_name = "secret_file"
    if update.message.reply_to_message:
        msg = update.message.reply_to_message
        if msg.photo:
            file_id, file_name = msg.photo[-1].file_id, f"photo_{msg.photo[-1].file_unique_id}.jpg"
        elif msg.video:
            file_id, file_name = msg.video.file_id, msg.video.file_name or f"video_{msg.video.file_unique_id}.mp4"
        elif msg.document:
            file_id, file_name = msg.document.file_id, msg.document.file_name or f"doc_{msg.document.file_unique_id}"
        elif msg.voice:
            file_id, file_name = msg.voice.file_id, f"voice_{msg.voice.file_unique_id}.ogg"
    if not file_id:
        last_media = memory.get_last_media(uid)
        if last_media and last_media.get("file_id"):
            file_id, file_name = last_media["file_id"], last_media["name"]
    if not file_id:
        await update.message.reply_text("Pehle photo/video bhejo ya us par reply karke vault mein add karo.")
        return
    label = " ".join(context.args) if context.args else "Secret"
    memory.add_vault_entry(uid, file_id, file_name, label, "")
    await update.message.reply_text(f"🔐 '{label}' vault mein add ho gaya.")


async def cmd_vault_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    if not memory.get_vault_code(uid):
        await update.message.reply_text("Pehle /vault_setcode se code set karo.")
        return
    if not _session_unlocked(context):
        if not context.args or not await _authenticate(update, context, context.args[0]):
            return
    entries = memory.get_vault_entries(uid)
    if not entries:
        await update.message.reply_text("🔐 Vault empty hai.")
        return
    text = "🔐 **Private Vault**\n\n" + "\n".join(f"• `{e['id']}` — {e['label']}" for e in entries)
    await update.message.reply_text(text, parse_mode="Markdown")


async def _get_entry(update, context):
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /vault_open <id> [code]")
        return None
    try:
        entry_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid vault ID.")
        return None
    if not _session_unlocked(context):
        if len(context.args) < 2 or not await _authenticate(update, context, context.args[1]):
            return None
    entries = context.application.bot_data["memory"].get_vault_entries(update.effective_user.id)
    return next((e for e in entries if e["id"] == entry_id), None)


async def cmd_vault_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    target = await _get_entry(update, context)
    if not target:
        await update.message.reply_text("Vault item nahi mili.")
        return
    await update.message.reply_text("🤫 Vault se nikal rahi hoon…")
    file_id = target["file_id"]
    name = (target.get("file_name") or "file").lower()
    caption = f"🔐 {target['label']}"
    try:
        if name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            await update.message.reply_photo(photo=file_id, caption=caption)
        elif name.endswith((".mp4", ".mov", ".webm")):
            await update.message.reply_video(video=file_id, caption=caption)
        elif name.endswith((".mp3", ".ogg", ".wav", ".m4a")):
            await update.message.reply_audio(audio=file_id, caption=caption)
        else:
            await update.message.reply_document(document=file_id, caption=caption)
    except Exception:
        logger.exception("vault open failed")
        await update.message.reply_text("Vault item send nahi ho paayi.")


async def cmd_vault_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    target = await _get_entry(update, context)
    if not target:
        await update.message.reply_text("Vault item nahi mili.")
        return
    context.application.bot_data["memory"].delete_vault_entry(update.effective_user.id, target["id"])
    await update.message.reply_text(f"🗑 Vault item `{target['id']}` delete ho gayi.", parse_mode="Markdown")
