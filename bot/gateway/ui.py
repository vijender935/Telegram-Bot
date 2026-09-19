"""Minimal Telegram presentation layer.

The bot is prompt-first: there is no feature menu, button grid, or command
catalog. /start only provides a short natural-language onboarding message.
"""

def home_text() -> str:
    return (
        "😈 AI Companion ready.\n\n"
        "Bas normal language mein bolo kya karna hai.\n"
        "Images, R2 data, search, processing, memory aur baaki supported tasks "
        "prompt se handle honge."
    )
