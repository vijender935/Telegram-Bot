"""Production bootstrap for the Telegram AI companion."""
from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from flask import Flask, jsonify
from waitress import serve
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters
from langchain_groq import ChatGroq

from bot import config
from bot.application.drive_service import DriveService
from bot.application.secure_memory import SecureMemory
from bot.application.vault_guard import VaultGuard
from bot.core.health import check_health
from bot.core.logging import configure_logging
from bot.core.security import SlidingWindowRateLimiter
from bot.domain.memory.service import MemoryService
from bot.gateway.commands import (
    cmd_clear,
    cmd_forgetprofile,
    cmd_fullreset,
    cmd_mood,
    cmd_profile,
    cmd_start,
    mood_callback,
)
from bot.gateway.handlers import handle_text
from bot.gateway.media import (
    cmd_delete,
    cmd_download,
    cmd_drive,
    cmd_enhance,
    cmd_list,
    cmd_search,
    cmd_upload,
    cmd_voice,
    enhance_callback,
    file_action_callback,
    handle_audio,
    handle_document,
    handle_photo,
    handle_video,
    handle_video_note,
    handle_voice,
)
from bot.gateway.scheduler import proactive_ping
from bot.gateway.settings import cmd_settings
from bot.gateway.vault import (
    cmd_vault_add,
    cmd_vault_del,
    cmd_vault_list,
    cmd_vault_open,
    cmd_vault_setcode,
)
from bot.infra.drive_client import DriveClient
from bot.infra.memory import MemoryStore
from bot.infra.sandbox import SandboxStorage
from bot.infra.serial_map import SerialMapStore
from bot.infrastructure.rag_mcp import RAGMCPClient
from bot.infrastructure.vectorstore.semantic_index import SemanticIndex

configure_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)
web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Telegram Bot v3 • healthy"


@web_app.route("/health")
def health():
    result = check_health(config, config.MEMORY_DB_PATH)
    rag = web_app.config.get("rag_mcp")
    result["rag_mcp"] = {
        "configured": bool(rag and rag.configured),
        "available": bool(rag and rag.available),
        "url": rag._safe_url() if rag else "",
        "tools": sorted(rag.tool_map) if rag else [],
        "last_error": rag.last_error if rag else "",
        "last_health": rag.last_health if rag else {},
    }
    return jsonify(result)


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

    rag_mcp = RAGMCPClient(
        config.RAG_MCP_URL if config.RAG_MCP_ENABLED else "",
        api_key=config.RAG_MCP_API_KEY,
        timeout=config.RAG_MCP_TIMEOUT_SECONDS,
        top_k=config.RAG_MCP_TOP_K,
        mode=config.RAG_MCP_MODE,
        retries=config.RAG_MCP_RETRIES,
    )
    await rag_mcp.initialize()
    if rag_mcp.configured:
        await rag_mcp.health()
    web_app.config["rag_mcp"] = rag_mcp

    llm = ChatGroq(model=config.GROQ_MODEL, groq_api_key=config.GROQ_API_KEY, temperature=config.TEMPERATURE)
    app = Application.builder().token(config.TELEGRAM_TOKEN).concurrent_updates(True).build()
    app.bot_data.update({
        "sandbox": sandbox,
        "memory": memory,
        "serial_store": serial_store,
        "drive": drive,
        "rag_mcp": rag_mcp,
        "rag_tools": rag_mcp.tools,
        "llm": llm,
        "groq_api_key": config.GROQ_API_KEY,
        "rate_limiter": SlidingWindowRateLimiter(config.RATE_LIMIT_PER_MINUTE, 60),
        "vault_guard": VaultGuard(config.VAULT_MAX_ATTEMPTS, config.VAULT_LOCKOUT_SECONDS),
    })

    handlers = [
        CommandHandler("start", cmd_start),
        CommandHandler("clear", cmd_clear),
        CommandHandler("profile", cmd_profile),
        CommandHandler("forgetprofile", cmd_forgetprofile),
        CommandHandler("fullreset", cmd_fullreset),
        CommandHandler("mood", cmd_mood),
        CommandHandler("settings", cmd_settings),
        CommandHandler("voice", cmd_voice),
        CommandHandler("vault_setcode", cmd_vault_setcode),
        CommandHandler("vault_add", cmd_vault_add),
        CommandHandler("vault_list", cmd_vault_list),
        CommandHandler("vault_open", cmd_vault_open),
        CommandHandler("vault_del", cmd_vault_del),
        CommandHandler("enhance", cmd_enhance),
        CommandHandler("drive", cmd_drive),
        CommandHandler("list", cmd_list),
        CommandHandler("download", cmd_download),
        CommandHandler("search", cmd_search),
        CommandHandler("upload", cmd_upload),
        CommandHandler("delete", cmd_delete),
        CallbackQueryHandler(mood_callback, pattern="^mood_"),
        CallbackQueryHandler(file_action_callback, pattern="^fileact_"),
        CallbackQueryHandler(enhance_callback, pattern="^enhance_"),
        CallbackQueryHandler(ui_callback, pattern="^ui_"),
        CallbackQueryHandler(settings_callback, pattern="^set_"),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text),
        MessageHandler(filters.Document.ALL, handle_document),
        MessageHandler(filters.PHOTO, handle_photo),
        MessageHandler(filters.VOICE, handle_voice),
        MessageHandler(filters.AUDIO, handle_audio),
        MessageHandler(filters.VIDEO, handle_video),
        MessageHandler(filters.VIDEO_NOTE, handle_video_note),
    ]
    for handler in handlers:
        app.add_handler(handler)
    app.add_error_handler(error_handler)
    if app.job_queue:
        app.job_queue.run_repeating(proactive_ping, interval=3600 * 6, first=3600)

    logger.info(
        "Bot v3 ready | model=%s | vision=%s | rag_mcp=%s tools=%s health=%s",
        config.GROQ_MODEL,
        config.GROQ_VISION_MODEL,
        rag_mcp.available,
        sorted(rag_mcp.tool_map),
        rag_mcp.last_health.get("status", "unknown"),
    )
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()


def main() -> None:
    threading.Thread(target=run_web, daemon=True, name="health-server").start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
