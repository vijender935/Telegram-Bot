"""Backward-compatible scheduler bootstrap."""
from bot.gateway.scheduler import proactive_ping


def start_scheduler(app, memory=None) -> None:
    """Register the existing proactive ping job on Telegram's JobQueue."""
    if app.job_queue:
        app.job_queue.run_repeating(proactive_ping, interval=3600 * 6, first=3600)


__all__ = ["proactive_ping", "start_scheduler"]
