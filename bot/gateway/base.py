"""Common Telegram gateway helpers."""
from bot import config


def _allowed(uid: int) -> bool:
    return config.PRIMARY_USER_ID is not None and uid == config.PRIMARY_USER_ID
