import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.domain.mood import MOODS, MOOD_MAP
from bot.domain.learning import profile_to_prompt_text
from bot.gateway.base import _allowed
from bot.gateway.ui import home_text, home_keyboard, settings_text

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    # /start no longer destroys conversation history.
    await update.message.reply_text(home_text(), reply_markup=home_keyboard())


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_history(update.effective_user.id)
    await update.message.reply_text("🧠 Chat history clear ho gayi. Profile aur long-term settings safe hain.")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    profile = memory.get_profile(update.effective_user.id)
    text = profile_to_prompt_text(profile)
    await update.message.reply_text("👤 **Your Profile**\n\n" + text, parse_mode="Markdown")


async def cmd_forgetprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_profile(update.effective_user.id)
    await update.message.reply_text("🧠 Profile clear ho gayi. Ab naye sir se learn karungi.")


async def cmd_fullreset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_all_for_user(update.effective_user.id)
    await update.message.reply_text("♻️ User data reset complete: history, profile, mood, memory aur vault metadata.")


async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    keyboard = [
        [InlineKeyboardButton("🧹 Clear chat history", callback_data="set_clear")],
        [InlineKeyboardButton("👤 Profile", callback_data="set_profile"), InlineKeyboardButton("🎭 Mood", callback_data="set_mood")],
        [InlineKeyboardButton("♻️ Reset user data", callback_data="set_reset")],
    ]
    await update.message.reply_text(settings_text(), reply_markup=InlineKeyboardMarkup(keyboard))


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id if update.effective_user else 0
    if not _allowed(uid):
        return
    keyboard = [[InlineKeyboardButton(t, callback_data=d)] for t, d in MOODS]
    target = update.message or update.callback_query.message
    await target.reply_text("🎭 **Choose your vibe**", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def mood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not _allowed(query.from_user.id):
        return
    selected = MOOD_MAP.get(query.data)
    if not selected:
        await query.edit_message_text("Invalid mood.")
        return
    memory = context.application.bot_data["memory"]
    memory.set_mood(query.from_user.id, selected)
    await query.edit_message_text(f"✅ Vibe set → *{selected}*", parse_mode="Markdown")
