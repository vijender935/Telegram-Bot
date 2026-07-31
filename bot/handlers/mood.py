from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


MOODS = [
    ("Soft / Romantic", "mood_soft"),
    ("Horny / Flirty", "mood_horny"),
    ("Rough / Punishment", "mood_rough"),
    ("Gay", "mood_gay"),
    ("Straight", "mood_straight"),
    ("Strapon / Pegging", "mood_strapon"),
    ("Femdom", "mood_femdom"),
    ("Switch / Mixed", "mood_switch"),
]

MOOD_MAP = {
    "mood_soft": "Soft / Romantic",
    "mood_horny": "Horny / Flirty",
    "mood_rough": "Rough / Punishment",
    "mood_gay": "Gay",
    "mood_straight": "Straight",
    "mood_strapon": "Strapon / Pegging",
    "mood_femdom": "Femdom",
    "mood_switch": "Switch / Mixed",
}


async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(text, callback_data=data)]
        for text, data in MOODS
    ]
    await update.message.reply_text(
        "🎭 Apna vibe choose karo:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def mood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected = MOOD_MAP.get(query.data)
    if not selected:
        await query.edit_message_text("Invalid mood.")
        return

    uid = query.from_user.id
    memory = context.application.bot_data["memory"]
    memory.set_mood(uid, selected)

    await query.edit_message_text(
        f"✅ Vibe set → *{selected}*\n\nAb main is mood mein baat karungi 😈",
        parse_mode="Markdown",
    )
