import asyncio
import logging
import threading

from flask import Flask
from telegram.ext import Application, CommandHandler, MessageHandler, filters
from langchain_groq import ChatGroq

from bot import config
from bot.services.drive import DriveService
from bot.services.sandbox import SandboxStorage
from bot.tools.agent_tools import build_tools
from bot.agent.personality import build_agent
from bot.handlers.text import handle_text, cmd_start, cmd_clear
from bot.handlers.media import handle_document, handle_photo, handle_voice
from bot.handlers.commands import (
    cmd_drive, cmd_list, cmd_download, cmd_search, cmd_upload, cmd_delete,
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
    return "Telegram Bot running 🔥"


def run_web():
    web_app.run(host="0.0.0.0", port=config.PORT)


async def run_bot():
    sandbox = SandboxStorage(config.SANDBOX_PATH)
    drive = DriveService(config.GOOGLE_FOLDER_ID, config.GOOGLE_SA_JSON)
    llm = ChatGroq(
        model=config.GROQ_MODEL,
        groq_api_key=config.GROQ_API_KEY,
        temperature=0.7,
    )
    tools = build_tools(drive, sandbox)
    agent = build_agent(llm, tools)

    app = Application.builder().token(config.TELEGRAM_TOKEN).build()
    app.bot_data["drive"] = drive
    app.bot_data["sandbox"] = sandbox
    app.bot_data["agent"] = agent

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("clear", cmd_clear))
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

    logger.info("Bot started")
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    await asyncio.Event().wait()


def main():
    threading.Thread(target=run_web, daemon=True).start()
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
