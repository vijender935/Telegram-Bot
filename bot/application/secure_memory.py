"""Thin compatibility facade over MemoryStore.

Vault support has been removed. This class remains only so existing imports
that expect a SecureMemory wrapper continue to work.
"""
from __future__ import annotations


class SecureMemory:
    def __init__(self, store):
        self.store = store

    def __getattr__(self, name):
        return getattr(self.store, name)

    def clear_all_for_user(self, user_id: int):
        self.store.clear_all_for_user(user_id)
