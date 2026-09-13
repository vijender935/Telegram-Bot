"""Backward-compatible import for the layered memory service."""
from bot.domain.memory.service import MemoryItem, MemoryService

__all__ = ["MemoryItem", "MemoryService"]
