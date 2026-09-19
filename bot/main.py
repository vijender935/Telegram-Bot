from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from flask import Flask, jsonify, request
from waitress import serve
from telegram import Update
from telegram.ext import CommandHandler, ContextTypes, Application, MessageHandler, filters

from bot import config
from bot.agent.chat_agent import build_llm
from bot.core.health import check_health
from bot.core.logging import configure_logging
from bot.gateway.commands import cmd_start
from bot.gateway.handlers import handle_text
from bot.gateway.media import (
    handle_audio,
    handle_document,
    handle_photo,
    handle_video,
    handle_video_note,
    handle_voice,
)
from bot.infra.memory import MemoryStore
from bot.infra.sandbox import SandboxStorage
from bot.infra.serial_map import SerialMapStore
from bot.infra.rag_mcp import CloudflareMCPClient
from bot.domain.memory_service import MemoryService
from bot.domain.semantic_index import SemanticIndex
from bot.domain.secure_memory import SecureMemory
from bot.core.rate_limit import SlidingWindowRateLimiter
from bot.scheduler import start_scheduler

configure_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)
web_app = Flask(__name__)
_BOT_LOOP: asyncio.AbstractEventLoop | None = None
_TELEGRAM_APP: Application | None = None


@web_app.route("/")
def home():
    return "Telegram Bot v3 • healthy"


@web_app.route("/health")
def health():
    result = check_health(config, config.MEMORY_DB_PATH)
    mcp = web_app.config.get("cloudflare_mcp")
    result["cloudflare_mcp"] = {
        "configured": bool(mcp and mcp.configured),
        "available": bool(mcp and mcp.available),
        "url": mcp._safe_url() if mcp else "",
        "tools": sorted(mcp.tool_map) if mcp else [],
        "last_error": mcp.last_error if mcp else "",
        "last_health": mcp.last_health if mcp else {},
    }
    return jsonify(result)


@web_app.post("/telegram")
def telegram_webhook():
    """Receive Telegram webhook updates and enqueue them on the bot event loop."""
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != config.TELEGRAM_WEBHOOK_SECRET:
        return jsonify({"error": "forbidden"}), 403
    if _BOT_LOOP is None or _TELEGRAM_APP is None:
        return jsonify({"error": "bot not ready"}), 503
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"error": "invalid json"}), 400
    try:
        update = Update.de_json(payload, bot=_TELEGRAM_APP.bot)
        _BOT_LOOP.call_soon_threadsafe(_TELEGRAM_APP.update_queue.put_nowait, update)
    except Exception:
        logger.exception("Telegram webhook update enqueue failed")
        return jsonify({"error": "enqueue failed"}), 500
    return "", 200


def run_web() -> None:
    serve(web_app, host="0.0.0.0", port=config.PORT, threads=4)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text("Temporary error aa gaya. Dobara try karo.")


async def run_bot() -> None:
    config.validate_startup()
    Path(config.SANDBOX_PATH).mkdir(parents=True, exist_ok=True)
    Path(config.MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    sandbox = SandboxStorage(config.SANDBOX_PATH)
    store = MemoryStore(config.MEMORY_DB_PATH)
    semantic_index = SemanticIndex(config.MEMORY_DB_PATH)
    memory = SecureMemory(MemoryService(store, semantic_index))
    serial_store = SerialMapStore(ttl_seconds=config.SERIAL_MAP_TTL_SECONDS, db_path=config.MEMORY_DB_PATH)

    cloudflare_mcp = CloudflareMCPClient(
        config.CLOUDFLARE_MCP_URL if config.CLOUDFLARE_MCP_ENABLED else "",
        api_key=config.CLOUDFLARE_MCP_API_KEY,
        timeout=config.CLOUDFLARE_MCP_TIMEOUT_SECONDS,
        retries=config.CLOUDFLARE_MCP_RETRIES,
    )
    await cloudflare_mcp.initialize()
    if cloudflare_mcp.configured:
        await cloudflare_mcp.health()
    web_app.config["cloudflare_mcp"] = cloudflare_mcp

    llm = build_llm()
    app = Application.builder().token(config.TELEGRAM_TOKEN).updater(None).concurrent_updates(False).build()
    app.bot_data.update({
        "sandbox": sandbox,
        "memory": memory,
        "serial_store": serial_store,
        "cloudflare_mcp": cloudflare_mcp,
        "mcp_tools": cloudflare_mcp.tools,
        "llm": llm,
        "groq_api_key": config.GROQ_API_KEY,
        "rate_limiter": SlidingWindowRateLimiter(config.RATE_LIMIT_PER_MINUTE, 60),
    })

    handlers = [
        CommandHandler("start", cmd_start),
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

    global _BOT_LOOP, _TELEGRAM_APP
    _BOT_LOOP = asyncio.get_running_loop()
    _TELEGRAM_APP = app
    threading.Thread(target=run_web, daemon=True).start()
    start_scheduler(app, memory)

    logger.info(
        "Bot v3 ready | model=%s | custom_cloudflare_mcp=%s tools=%s health=%s",
        config.GROQ_MODEL,
        cloudflare_mcp.available,
        sorted(cloudflare_mcp.tool_map),
        cloudflare_mcp.last_health,
    )

    await app.initialize()
    await app.start()
    webhook_url = f"{config.TELEGRAM_WEBHOOK_URL}/telegram"
    await app.bot.set_webhook(
        url=webhook_url,
        secret_token=config.TELEGRAM_WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )
    logger.info("Telegram webhook active url=%s", webhook_url)
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        # Do not delete the webhook during Render's overlap window: an old
        # instance may shut down after a new instance has already installed it.
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(run_bot())
