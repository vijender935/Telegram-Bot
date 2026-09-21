from __future__ import annotations

import asyncio
import logging
import threading
from pathlib import Path

from waitress import serve
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters

from bot import config
from bot.api.app import create_http_app
from bot.api.auth import ApiKeyStore
from bot.application.chat_service import ChatService
from bot.agent.chat_agent import build_groq_llm
from bot.core.health import check_health
from bot.core.logging import configure_logging
from bot.core.observability import metrics
from bot.core.rate_limit import SlidingWindowRateLimiter
from bot.gateway.commands import cmd_start, cmd_help, cmd_profile, cmd_memory, cmd_reset, handle_settings
from bot.gateway.handlers import handle_text
from bot.gateway.media import handle_audio, handle_document, handle_photo, handle_video, handle_video_note, handle_voice, cmd_voice
from bot.infrastructure.memory import MemoryStore
from bot.infrastructure.sandbox import SandboxStorage
from bot.infrastructure.serial_map import SerialMapStore
from bot.infrastructure.rag_mcp import CloudflareMCPClient
from bot.domain.memory.service import MemoryService
from bot.infrastructure.vectorstore.semantic_index import SemanticIndex
from bot.gateway.scheduler import start_scheduler

configure_logging(config.LOG_LEVEL)
logger = logging.getLogger(__name__)

_BOT_LOOP: asyncio.AbstractEventLoop | None = None
_TELEGRAM_APP: Application | None = None


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Unhandled Telegram update", exc_info=context.error)
    metrics.inc("telegram.errors")
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "⚠️ Ek temporary issue aa gaya. Request ID logs mein record ho gayi hai. Dobara try karo."
            )
        except Exception:
            logger.exception("Telegram error response failed")


def run_web(http_app) -> None:
    serve(http_app, host="0.0.0.0", port=config.PORT, threads=8)


async def run_bot() -> None:
    global _BOT_LOOP, _TELEGRAM_APP

    config.validate_startup()
    Path(config.SANDBOX_PATH).mkdir(parents=True, exist_ok=True)
    Path(config.MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    sandbox = SandboxStorage(config.SANDBOX_PATH)
    store = MemoryStore(config.MEMORY_DB_PATH)
    semantic_index = SemanticIndex(config.MEMORY_DB_PATH)
    memory = MemoryService(store, semantic_index)
    serial_store = SerialMapStore(
        ttl_seconds=config.SERIAL_MAP_TTL_SECONDS,
        db_path=config.MEMORY_DB_PATH,
    )

    cloudflare_mcp = CloudflareMCPClient(
        config.CLOUDFLARE_MCP_URL if config.CLOUDFLARE_MCP_ENABLED else "",
        api_key=config.CLOUDFLARE_MCP_API_KEY,
        timeout=config.CLOUDFLARE_MCP_TIMEOUT_SECONDS,
        retries=config.CLOUDFLARE_MCP_RETRIES,
    )
    llm = build_groq_llm()
    api_keys = ApiKeyStore(config.MEMORY_DB_PATH)

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .updater(None)
        .concurrent_updates(False)
        .build()
    )

    app.bot_data.update({
        "sandbox": sandbox,
        "memory": memory,
        "serial_store": serial_store,
        "cloudflare_mcp": cloudflare_mcp,
        "mcp_tools": [],
        "llm": llm,
        "groq_api_key": config.GROQ_API_KEY,
        "rate_limiter": SlidingWindowRateLimiter(config.RATE_LIMIT_PER_MINUTE, 60),
    })

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("memory", cmd_memory))
    app.add_handler(CommandHandler("reset", cmd_reset))
    app.add_handler(CommandHandler("voice", cmd_voice))
    app.add_handler(CallbackQueryHandler(handle_settings, pattern=r"^(settings|memory|reset):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))
    app.add_error_handler(error_handler)

    _BOT_LOOP = asyncio.get_running_loop()

    await app.initialize()
    await app.start()
    _TELEGRAM_APP = app

    chat_service = ChatService(memory, llm, [])
    http_app = create_http_app()
    http_app.config.update({
        "memory": memory,
        "api_key_store": api_keys,
        "admin_api_key": config.ADMIN_API_KEY,
        "chat_service": chat_service,
        "bot_loop": _BOT_LOOP,
        "api_timeout_seconds": config.API_TIMEOUT_SECONDS,
        "model_name": config.GROQ_MODEL,
        "metrics_snapshot": metrics.snapshot,
    })
    http_app.config["cloudflare_mcp"] = cloudflare_mcp
    threading.Thread(target=run_web, args=(http_app,), daemon=True, name="http-server").start()

    start_scheduler(app)

    async def initialize_mcp_background() -> None:
        try:
            tools = await cloudflare_mcp.initialize()
            app.bot_data["mcp_tools"] = tools
            chat_service.mcp_tools = list(tools)
            if tools:
                await cloudflare_mcp.health()
            logger.info(
                "MCP ready available=%s tools=%s error=%s",
                cloudflare_mcp.available,
                sorted(cloudflare_mcp.tool_map),
                cloudflare_mcp.last_error,
            )
        except Exception:
            logger.exception("MCP background initialization failed")

    asyncio.create_task(initialize_mcp_background(), name="cloudflare-mcp-init")

    webhook_url = f"{config.TELEGRAM_WEBHOOK_URL}/telegram"
    await app.bot.set_webhook(
        url=webhook_url,
        secret_token=config.TELEGRAM_WEBHOOK_SECRET,
        allowed_updates=Update.ALL_TYPES,
    )

    logger.info(
        "Production bot ready model=%s webhook=%s api=/v1",
        config.GROQ_MODEL,
        webhook_url,
    )

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(run_bot())
