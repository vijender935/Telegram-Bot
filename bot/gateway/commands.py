"""User-facing Telegram command and settings surface."""
from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.gateway.ui import home_text, help_text, profile_text, memory_text


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Settings", callback_data="settings:open")],
        [InlineKeyboardButton("🧠 Memory", callback_data="memory:show"),
         InlineKeyboardButton("♻️ Reset chat", callback_data="reset:confirm")],
    ])
    await update.message.reply_text(home_text(update.effective_user.first_name), reply_markup=keyboard)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(help_text())


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    memory = context.application.bot_data["memory"]
    await update.message.reply_text(profile_text(memory.get_profile(update.effective_user.id)))


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    memory = context.application.bot_data["memory"]
    summary, count = memory.get_session(update.effective_user.id)
    await update.message.reply_text(memory_text(summary, count))


async def cmd_reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.effective_user or not update.message:
        return
    memory = context.application.bot_data["memory"]
    memory.clear_all_for_user(update.effective_user.id)
    await update.message.reply_text("♻️ Chat history aur saved memory reset kar di.")


async def handle_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not update.effective_user:
        return
    await query.answer()
    action = query.data or ""
    memory = context.application.bot_data["memory"]
    uid = update.effective_user.id

    if action == "settings:open":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Profile", callback_data="settings:profile")],
            [InlineKeyboardButton("🧠 Memory", callback_data="memory:show")],
            [InlineKeyboardButton("♻️ Reset everything", callback_data="reset:confirm")],
        ])
        await query.edit_message_text("⚙️ Settings\n\nYahan se profile aur memory manage kar sakte ho.", reply_markup=keyboard)
    elif action == "settings:profile":
        await query.edit_message_text(profile_text(memory.get_profile(uid)))
    elif action == "memory:show":
        summary, count = memory.get_session(uid)
        await query.edit_message_text(memory_text(summary, count))
    elif action == "reset:confirm":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Yes, reset", callback_data="reset:do"),
             InlineKeyboardButton("Cancel", callback_data="settings:open")]
        ])
        await query.edit_message_text("⚠️ Current history, profile aur saved memory clear kar du?", reply_markup=keyboard)
    elif action == "reset:do":
        memory.clear_all_for_user(uid)
        await query.edit_message_text("♻️ Sab reset ho gaya. Fresh start.")
