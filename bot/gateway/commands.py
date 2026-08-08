import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.domain.mood import MOODS, MOOD_MAP
from bot.domain.learning import profile_to_prompt_text
from bot.gateway.base import _allowed

logger = logging.getLogger(__name__)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_history(update.effective_user.id)
    
    welcome_text = (
        "Hlo 😈\n\n"
        "Main update ho gayi hoon! Ab mere paas:\n"
        "🕒 **Time Awareness:** Main waqt ke hisaab se react karungi.\n"
        "🎙 **Voice Notes:** Kisi bhi reply ke baad `/voice` likho, main bol kar sunaungi.\n"
        "👁 **Enhanced Vision:** Photos par mere reactions ab aur bhi personal honge.\n"
        "🎭 **Dynamic Moods:** `/mood` se mera vibe change karo.\n\n"
        "Batao, aaj raat kya plan hai? 😏"
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_history(update.effective_user.id)
    await update.message.reply_text("Chat history saaf 🔥 (profile same rahega — /forgetprofile se profile bhi)")

async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    profile = memory.get_profile(update.effective_user.id)
    text = profile_to_prompt_text(profile)
    await update.message.reply_text(
        "🧠 Jo maine tere baare mein seekha:\n\n" + text +
        "\n\n/forgetprofile — yeh bhool jaaun"
    )

async def cmd_forgetprofile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_profile(update.effective_user.id)
    await update.message.reply_text("Profile bhool gayi. Naye sir se seekhungi 🔥")

async def cmd_fullreset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    memory = context.application.bot_data["memory"]
    memory.clear_all_for_user(update.effective_user.id)
    await update.message.reply_text("Sab kuch saaf 🔥 History + Profile + Mood + Memory reset. Naye sir se shuru.")

async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not _allowed(update.effective_user.id):
        return
    keyboard = [[InlineKeyboardButton(t, callback_data=d)] for t, d in MOODS]
    await update.message.reply_text(
        "🎭 Apna vibe choose karo:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

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
    await query.edit_message_text(
        f"✅ Vibe set → *{selected}*\n\nAb is mood mein baat karungi 😈",
        parse_mode="Markdown",
    )
