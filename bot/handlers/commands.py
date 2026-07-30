from telegram import Update
from telegram.ext import ContextTypes
from bot.handlers.text import send_long_text, send_download


async def cmd_drive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive = context.application.bot_data["drive"]
    await send_long_text(update, drive.list_files("root"))


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive = context.application.bot_data["drive"]
    sub = " ".join(context.args) if context.args else "root"
    await send_long_text(update, drive.list_files(sub))


async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive = context.application.bot_data["drive"]
    sandbox = context.application.bot_data["sandbox"]
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Usage: /download <number>\nPehle /drive chalao.")
        return
    await send_download(update, drive, sandbox, int(context.args[0]))


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive = context.application.bot_data["drive"]
    if not context.args:
        await update.message.reply_text("Usage: /search <query>")
        return
    await send_long_text(update, drive.search(" ".join(context.args)))


async def cmd_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    drive = context.application.bot_data["drive"]
    sandbox = context.application.bot_data["sandbox"]
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
    sandbox = context.application.bot_data["sandbox"]
    if not context.args:
        await update.message.reply_text("Usage: /delete <filename>")
        return
    try:
        sandbox.delete(context.args[0])
        await update.message.reply_text(f"Deleted: {context.args[0]}")
    except Exception as e:
        await update.message.reply_text(str(e))
