"""Production bootstrap for the Telegram AI companion."""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from flask import Flask, jsonify
from waitress import serve
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from langchain_groq import ChatGroq

from bot import config
from bot.core.logging import configure_logging
from bot.core.health import check_health
from bot.core.security import SlidingWindowRateLimiter
from bot.infra.sandbox import SandboxStorage
from bot.infra.memory import MemoryStore
from bot.infra.serial_map import SerialMapStore
from bot.infra.drive_client import DriveClient
from bot.infrastructure.vectorstore.semantic_index import SemanticIndex
from bot.application.drive_service import DriveService
from bot.application.vault_guard import VaultGuard
from bot.application.secure_memory import SecureMemory
from bot.domain.memory.service import MemoryService
from bot.gateway.handlers import handle_text
from bot.gateway.commands import cmd_start, cmd_clear, cmd_profile, cmd_forgetprofile, cmd_fullreset, cmd_mood, mood_callback
from bot.gateway.settings import cmd_settings
from bot.gateway.media import (
    cmd_voice, cmd_drive, cmd_list, cmd_download, cmd_search, cmd_upload, cmd_delete,
    handle_photo, handle_document, handle_voice, handle_audio, handle_video, handle_video_note,
    file_action_callback, enhance_callback, cmd_enhance,
)
from bot.gateway.vault import cmd_vault_setcode, cmd_vault_add, cmd_vault_list, cmd_vault_open, cmd_vault_del
from bot.gateway.scheduler import proactive_ping

configure_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)
web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Telegram Bot v3 • healthy"


@web_app.route("/health")
def health():
    return jsonify(check_health(config, config.MEMORY_DB_PATH))


def run_web() -> None:
    serve(web_app, host="0.0.0.0", port=config.PORT, threads=4)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Temporary error aa gaya. Dobara try karo.")


async def ui_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if query.data == "ui_mood":
        await cmd_mood(update, context)
    elif query.data == "ui_profile":
        await query.edit_message_text("👤 Profile: /profile")
    elif query.data == "ui_settings":
        await query.edit_message_text("⚙️ Settings: /settings")
    elif query.data == "ui_drive":
        await query.edit_message_text("☁️ Drive: /drive • /search • /download")
    elif query.data == "ui_vault":
        await query.edit_message_text("🔐 Vault: /vault_setcode • /vault_list • /vault_open")
    elif query.data == "ui_voice":
        await query.edit_message_text("🎙 Last reply ke liye /voice use karo.")
    elif query.data == "ui_memory":
        await query.edit_message_text("🧠 Memory active hai. /clear sirf chat history clear karta hai.")


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    memory = context.application.bot_data["memory"]
    uid = query.from_user.id
    if query.data == "set_clear":
        memory.clear_history(uid)
        await query.edit_message_text("🧠 Chat history clear ho gayi. Profile safe hai.")
    elif query.data == "set_profile":
        await query.edit_message_text("👤 Profile: /profile")
    elif query.data == "set_mood":
        await query.edit_message_text("🎭 Mood: /mood")
    elif query.data == "set_reset":
        memory.clear_all_for_user(uid)
        await query.edit_message_text("♻️ User data reset complete.")


async def run_bot() -> None:
    config.validate_startup()
    Path(config.SANDBOX_PATH).mkdir(parents=True, exist_ok=True)
    Path(config.MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    sandbox = SandboxStorage(config.SANDBOX_PATH)
    store = MemoryStore(config.MEMORY_DB_PATH)
    semantic_index = SemanticIndex(config.MEMORY_DB_PATH)
    memory = SecureMemory(MemoryService(store, semantic_index))
    serial_store = SerialMapStore(ttl_seconds=config.SERIAL_MAP_TTL_SECONDS, db_path=config.MEMORY_DB_PATH)

    drive = None
    if config.GOOGLE_FOLDER_ID and config.GOOGLE_SA_JSON:
        try:
            client = DriveClient(config.GOOGLE_FOLDER_ID, config.GOOGLE_SA_JSON, serial_store)
            drive = DriveService(client, semantic_index)
            logger.info("Drive + semantic index initialized")
        except Exception:
            logger.exception("Drive init failed; continuing without Drive")

    llm = ChatGroq(model=config.GROQ_MODEL, groq_api_key=config.GROQ_API_KEY, temperature=config.TEMPERATURE)
    app = Application.builder().token(config.TELEGRAM_TOKEN).concurrent_updates(True).build()
    app.bot_data.update({
        "sandbox": sandbox, "memory": memory, "serial_store": serial_store, "drive": drive,
        "llm": llm, "groq_api_key": config.GROQ_API_KEY,
        "rate_limiter": SlidingWindowRateLimiter(config.RATE_LIMIT_PER_MINUTE, 60),
        "vault_guard": VaultGuard(config.VAULT_MAX_ATTEMPTS, config.VAULT_LOCKOUT_SECONDS),
    })

    for handler in [
        CommandHandler("start", cmd_start), CommandHandler("clear", cmd_clear), CommandHandler("profile", cmd_profile),
        CommandHandler("forgetprofile", cmd_forgetprofile), CommandHandler("fullreset", cmd_fullreset), CommandHandler("mood", cmd_mood),
        CommandHandler("settings", cmd_settings), CommandHandler("voice", cmd_voice), CommandHandler("vault_setcode", cmd_vault_setcode),
        CommandHandler("vault_add", cmd_vault_add), CommandHandler("vault_list", cmd_vault_list), CommandHandler("vault_open", cmd_vault_open),
        CommandHandler("vault_del", cmd_vault_del), CommandHandler("enhance", cmd_enhance), CommandHandler("drive", cmd_drive),
        CommandHandler("list", cmd_list), CommandHandler("download", cmd_download), CommandHandler("search", cmd_search),
        CommandHandler("upload", cmd_upload), CommandHandler("delete", cmd_delete), CallbackQueryHandler(mood_callback, pattern="^mood_"),
        CallbackQueryHandler(file_action_callback, pattern="^fileact_"), CallbackQueryHandler(enhance_callback, pattern="^enhance_"),
        CallbackQueryHandler(ui_callback, pattern="^ui_"), CallbackQueryHandler(settings_callback, pattern="^set_"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text), MessageHandler(filters.Document.ALL, handle_document),
        MessageHandler(filters.PHOTO, handle_photo), MessageHandler(filters.VOICE, handle_voice), MessageHandler(filters.AUDIO, handle_audio),
        MessageHandler(filters.VIDEO, handle_video), MessageHandler(filters.VIDEO_NOTE, handle_video_note),
    ]:
        app.add_handler(handler)
    app.add_error_handler(error_handler)
    if app.job_queue:
        app.job_queue.run_repeating(proactive_ping, interval=3600 * 6, first=3600)

    logger.info("Bot v3 ready | model=%s | vision=%s", config.GROQ_MODEL, config.GROQ_VISION_MODEL)
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()


def main() -> None:
    threading.Thread(target=run_web, daemon=True, name="health-server").start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
