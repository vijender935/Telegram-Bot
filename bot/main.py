import asyncio
import logging
import threading
from pathlib import Path

from flask import Flask
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from langchain_groq import ChatGroq

from bot import config
from bot.infra.sandbox import SandboxStorage
from bot.infra.memory import MemoryStore
from bot.infra.serial_map import SerialMapStore
from bot.infra.drive_client import DriveClient
from bot.agent.tools import build_tools
from bot.gateway.handlers import (
    cmd_start, cmd_clear, cmd_profile, cmd_forgetprofile, cmd_mood, mood_callback,
    cmd_drive, cmd_list, cmd_download, cmd_search, cmd_upload, cmd_delete,
    handle_text, handle_document, handle_photo, handle_voice,
    handle_audio, handle_video, handle_video_note, file_action_callback,
)

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("googleapiclient").setLevel(logging.WARNING)

web_app = Flask(__name__)


@web_app.route("/")
def home():
    return "Telegram Bot v2 running 🔥"


def run_web():
    web_app.run(host="0.0.0.0", port=config.PORT)


async def run_bot():
    Path(config.SANDBOX_PATH).mkdir(parents=True, exist_ok=True)
    Path(config.MEMORY_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    sandbox = SandboxStorage(config.SANDBOX_PATH)
    memory = MemoryStore(config.MEMORY_DB_PATH)
    serial_db = str(Path(config.MEMORY_DB_PATH).with_name("serial_map.db"))
    serial_store = SerialMapStore(
        ttl_seconds=config.SERIAL_MAP_TTL_SECONDS,
        db_path=serial_db,
    )
    drive = DriveClient(config.GOOGLE_FOLDER_ID, config.GOOGLE_SA_JSON, serial_store)
    llm = ChatGroq(
        model=config.GROQ_MODEL,
        groq_api_key=config.GROQ_API_KEY,
        temperature=config.TEMPERATURE,
    )
    tools = build_tools()

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .connect_timeout(30)
        .pool_timeout(30)
        .build()
    )

    app.bot_data["drive"] = drive
    app.bot_data["sandbox"] = sandbox
    app.bot_data["memory"] = memory
    app.bot_data["llm"] = llm
    app.bot_data["tools"] = tools
    app.bot_data["groq_api_key"] = config.GROQ_API_KEY

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("forgetprofile", cmd_forgetprofile))
    app.add_handler(CommandHandler("mood", cmd_mood))
    app.add_handler(CallbackQueryHandler(mood_callback, pattern="^mood_"))
    app.add_handler(CallbackQueryHandler(file_action_callback, pattern="^fileact_"))
    app.add_handler(CommandHandler("drive", cmd_drive))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("download", cmd_download))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("upload", cmd_upload))
    app.add_handler(CommandHandler("delete", cmd_delete))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.AUDIO, handle_audio))
    app.add_handler(MessageHandler(filters.VIDEO, handle_video))
    app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_video_note))

    logger.info(
        "Bot v2 started | temp=%s | vision=%s | describe=%s",
        config.TEMPERATURE,
        config.GROQ_VISION_MODEL,
        config.MEDIA_DESCRIBE_ON_DOWNLOAD,
    )
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()


def main():
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
