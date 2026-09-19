"""Minimal Telegram command surface.

Only /start is kept because Telegram clients commonly use it to bootstrap a
conversation. All actual capabilities are prompt-driven.
"""
from telegram import Update
from telegram.ext import ContextTypes

from bot.gateway.base import _allowed
from bot.gateway.ui import home_text


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not _allowed(update.effective_user.id):
        return
    await update.message.reply_text(home_text())
