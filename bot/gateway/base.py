"""Common Telegram gateway helpers."""


def _allowed(uid: int) -> bool:
    """Compatibility helper: the bot has no user authorization layer."""
    return True
