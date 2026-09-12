"""Layered memory facade for history, profile and semantic episodic retrieval."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryItem:
    text: str
    importance: float = 0.5
    created_at: float = 0.0


class MemoryService:
    """Keep short-term state in SQLite while exposing user-scoped semantic memory."""

    def __init__(self, store, semantic_index=None):
        self.store = store
        self.semantic_index = semantic_index

    def __getattr__(self, name):
        return getattr(self.store, name)

    def remember(self, user_id: int, text: str, importance: float = 0.5) -> MemoryItem:
        item = MemoryItem(
            text=(text or "").strip()[:2000],
            importance=max(0.0, min(1.0, importance)),
            created_at=time.time(),
        )
        if item.text and self.semantic_index:
            key = f"memory:{user_id}:{int(item.created_at * 1000)}"
            self.semantic_index.upsert(key, item.text)
        return item

    def search(self, query: str, limit: int = 10):
        if not self.semantic_index:
            return []
        return self.semantic_index.search(query, limit, prefix="memory:") if False else self.semantic_index.search(
            query, limit, prefix=f"memory:{int(0)}:"
        )

    def search_user(self, user_id: int, query: str, limit: int = 10):
        if not self.semantic_index:
            return []
        return self.semantic_index.search(query, limit, prefix=f"memory:{user_id}:")
