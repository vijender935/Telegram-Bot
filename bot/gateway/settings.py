from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.gateway.base import _allowed
from bot.gateway.ui import settings_text


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Clear chat", callback_data="set_clear")],
        [InlineKeyboardButton("👤 Profile", callback_data="set_profile"), InlineKeyboardButton("🎭 Mood", callback_data="set_mood")],
        [InlineKeyboardButton("🔐 Privacy reset", callback_data="set_reset")],
    ])
    await update.message.reply_text(settings_text(), reply_markup=keyboard)
