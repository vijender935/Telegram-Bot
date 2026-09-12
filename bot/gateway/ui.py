"""Telegram presentation layer: consistent, compact, button-first UI."""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def home_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🧠 Memory", callback_data="ui_memory"), InlineKeyboardButton("🎭 Mood", callback_data="ui_mood")],
        [InlineKeyboardButton("☁️ Drive", callback_data="ui_drive"), InlineKeyboardButton("🔐 Vault", callback_data="ui_vault")],
        [InlineKeyboardButton("🎙 Voice", callback_data="ui_voice"), InlineKeyboardButton("👤 Profile", callback_data="ui_profile")],
        [InlineKeyboardButton("⚙️ Settings", callback_data="ui_settings")],
    ])


def home_text() -> str:
    return (
        "╭────────────────────────────╮\n"
        "│       😈 AI COMPANION      │\n"
        "│                            │\n"
        "│  🧠 Memory   •  🎭 Persona │\n"
        "│  👁 Vision   •  ☁️ Drive   │\n"
        "│  🎙 Voice    •  🔐 Vault   │\n"
        "╰────────────────────────────╯\n\n"
        "Ready. Batao kya karna hai?"
    )


def settings_text() -> str:
    return (
        "╭─ ⚙️ Settings ─────────────╮\n"
        "│ 🤖 AI model & creativity  │\n"
        "│ 🧠 Memory controls        │\n"
        "│ 🎭 Persona & mood         │\n"
        "│ 🔐 Privacy & vault        │\n"
        "╰───────────────────────────╯"
    )
