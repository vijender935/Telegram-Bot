"""Security-aware compatibility facade for vault credentials.

Existing legacy vault hashes remain readable; the first successful legacy verification is
upgraded to PBKDF2-SHA256. New codes always use the v2 format.
"""
from __future__ import annotations

import sqlite3
import time
from bot.core.security import hash_secret, verify_secret


class SecureMemory:
    def __init__(self, store):
        self.store = store
        self.db_path = store._db_path
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS vault_codes_v2 (user_id INTEGER PRIMARY KEY, code_hash TEXT NOT NULL, updated_at REAL NOT NULL)")

    def __getattr__(self, name):
        return getattr(self.store, name)

    def set_vault_code(self, user_id: int, code: str):
        encoded = hash_secret(code)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("INSERT INTO vault_codes_v2(user_id,code_hash,updated_at) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET code_hash=excluded.code_hash,updated_at=excluded.updated_at", (user_id, encoded, time.time()))

    def get_vault_code(self, user_id: int):
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT code_hash FROM vault_codes_v2 WHERE user_id=?", (user_id,)).fetchone()
        return row[0] if row else self.store.get_vault_code(user_id)

    def verify_vault_code(self, user_id: int, code: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute("SELECT code_hash FROM vault_codes_v2 WHERE user_id=?", (user_id,)).fetchone()
        if row:
            return verify_secret(code, row[0])
        # Backwards-compatible migration from the old SHA-256 format.
        legacy = self.store.get_vault_code(user_id)
        if not legacy:
            return False
        import hashlib
        ok = legacy == hashlib.sha256(code.encode()).hexdigest()
        if ok:
            self.set_vault_code(user_id, code)
        return ok
