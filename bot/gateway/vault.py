import logging
from telegram import Update
from telegram.ext import ContextTypes
from bot.gateway.base import _allowed

logger = logging.getLogger(__name__)

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
    
    file_id = None
    file_name = "secret_file"
    
    if update.message.reply_to_message:
        msg = update.message.reply_to_message
        if msg.photo:
            file_id = msg.photo[-1].file_id
            file_name = f"photo_{msg.photo[-1].file_unique_id}.jpg"
        elif msg.video:
            file_id = msg.video.file_id
            file_name = msg.video.file_name or f"video_{msg.video.file_unique_id}.mp4"
        elif msg.document:
            file_id = msg.document.file_id
            file_name = msg.document.file_name or f"doc_{msg.document.file_unique_id}"
        elif msg.voice:
            file_id = msg.voice.file_id
            file_name = f"voice_{msg.voice.file_unique_id}.ogg"
    
    if not file_id:
        last_media = memory.get_last_media(uid)
        if last_media and last_media.get("file_id"):
            file_id = last_media["file_id"]
            file_name = last_media["name"]
        
    if not file_id:
        await update.message.reply_text("Pehle koi photo ya video bhej do, ya kisi purani photo par reply karke 'vault mein daal do' bolo. 😏")
        return
    
    label = " ".join(context.args) if context.args else "Secret"
    memory.add_vault_entry(uid, file_id, file_name, label, "")
    await update.message.reply_text(f"🔒 Yeh memory ('{label}') ab hamare secret vault mein safe hai. Sirf hamare liye... 😈")

async def cmd_vault_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    
    if not memory.get_vault_code(uid):
        await update.message.reply_text("Pehle /vault_setcode se ek code set karo.")
        return
    
    code = context.args[0] if context.args else ""
    if not memory.verify_vault_code(uid, code):
        await update.message.reply_text("❌ Galat code! Vault kholne ke liye sahi code chahiye... try again. 😏")
        return
    
    entries = memory.get_vault_entries(uid)
    if not entries:
        await update.message.reply_text("Vault abhi khali hai. Kuch 'khas' add karo na... 😈")
        return
    
    text = "🔒 **Hamari Secret Yaadein:**\n\n"
    for e in entries:
        text += f"ID: `{e['id']}` | Label: *{e['label']}*\n"
    
    text += "\nKholne ke liye: `/vault_open <id> <code>`"
    await update.message.reply_text(text, parse_mode="Markdown")

async def cmd_vault_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /vault_open <id> <code>")
        return
    
    try:
        entry_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID sahi nahi hai.")
        return
        
    code = context.args[1]
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    
    if not memory.verify_vault_code(uid, code):
        await update.message.reply_text("❌ Galat code! Tumhe lagta hai main itni asani se dikha dungi? 😏")
        return
    
    entries = memory.get_vault_entries(uid)
    target = next((e for e in entries if e["id"] == entry_id), None)
    
    if not target:
        await update.message.reply_text("Yeh ID toh nahi mili.")
        return
    
    await update.message.reply_text("Ruko, vault se nikal rahi hoon... 🤫")
    
    file_id = target["file_id"]
    name = (target.get("file_name") or "file").lower()
    caption = f"Hamari memory: {target['label']}"
    
    try:
        if name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            await update.message.reply_photo(photo=file_id, caption=caption)
        elif name.endswith((".mp4", ".mov", ".webm")):
            await update.message.reply_video(video=file_id, caption=caption)
        elif name.endswith((".mp3", ".ogg", ".wav", ".m4a")):
            await update.message.reply_audio(audio=file_id, caption=caption)
        else:
            await update.message.reply_document(document=file_id, caption=caption)
    except Exception as e:
        logger.exception("vault open failed")
        await update.message.reply_text(f"Error: {e}")

async def cmd_vault_del(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /vault_del <id> <code>")
        return
    
    try:
        entry_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("ID sahi nahi hai.")
        return
        
    code = context.args[1]
    uid = update.effective_user.id
    memory = context.application.bot_data["memory"]
    
    if not memory.verify_vault_code(uid, code):
        await update.message.reply_text("❌ Galat code!")
        return
    
    memory.delete_vault_entry(uid, entry_id)
    await update.message.reply_text(f"✅ Memory ID {entry_id} delete ho gayi. Ab wo sirf hamare dimaag mein rahegi... 😈")
