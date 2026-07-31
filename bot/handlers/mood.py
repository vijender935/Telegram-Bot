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

<<<<<<< HEAD
=======
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

>>>>>>> 5336183 (Adding Transcript)

async def cmd_mood(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton(text, callback_data=data)]
        for text, data in MOODS
    ]
<<<<<<< HEAD
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🎭 Apna vibe choose karo:",
        reply_markup=reply_markup
=======
    await update.message.reply_text(
        "🎭 Apna vibe choose karo:",
        reply_markup=InlineKeyboardMarkup(keyboard)
>>>>>>> 5336183 (Adding Transcript)
    )


async def mood_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

<<<<<<< HEAD
    mood_map = {
        "mood_soft": "Soft / Romantic",
        "mood_horny": "Horny / Flirty",
        "mood_rough": "Rough / Punishment",
        "mood_gay": "Gay",
        "mood_straight": "Straight",
        "mood_strapon": "Strapon / Pegging",
        "mood_femdom": "Femdom",
        "mood_switch": "Switch / Mixed",
    }

    selected = mood_map.get(query.data)
=======
    selected = MOOD_MAP.get(query.data)
>>>>>>> 5336183 (Adding Transcript)
    if not selected:
        await query.edit_message_text("Invalid mood.")
        return

    uid = query.from_user.id
<<<<<<< HEAD
    if "user_moods" not in context.application.bot_data:
        context.application.bot_data["user_moods"] = {}
    context.application.bot_data["user_moods"][uid] = selected
=======
    memory = context.application.bot_data["memory"]
    memory.set_mood(uid, selected)  # ✅ SQLite mein save — restart safe
>>>>>>> 5336183 (Adding Transcript)

    await query.edit_message_text(
        f"✅ Vibe set → *{selected}*\n\nAb main is mood mein baat karungi 😈",
        parse_mode="Markdown"
    )
