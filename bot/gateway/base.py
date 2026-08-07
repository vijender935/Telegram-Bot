import logging
from bot import config

logger = logging.getLogger(__name__)

def _allowed(uid: int) -> bool:
    if not config.ALLOWED_USER_IDS:
        return True
    return uid in config.ALLOWED_USER_IDS

def _get_drive(context):
    """Drive client return karo. None agar credentials missing hain."""
    return context.application.bot_data.get("drive")
