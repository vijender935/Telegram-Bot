"""Backward-compatible import for the renamed Drive client module."""
from bot.infra.drive_client import DriveClient

__all__ = ["DriveClient"]
