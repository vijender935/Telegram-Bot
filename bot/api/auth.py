"""API-key authentication and lifecycle management."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

PREFIX = "tb_live_"


@dataclass(frozen=True)
class ApiPrincipal:
    key_id: str
    name: str
    scopes: frozenset[str]


class ApiKeyStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                scopes TEXT NOT NULL DEFAULT 'chat:write,profile:read',
                created_at REAL NOT NULL,
                last_used_at REAL,
                revoked_at REAL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash)")

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create(self, name: str, scopes: list[str] | None = None) -> tuple[str, str]:
        token = PREFIX + secrets.token_urlsafe(32)
        key_id = "key_" + secrets.token_hex(8)
        scope_text = ",".join(sorted(set(scopes or ["chat:write", "profile:read"])))
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO api_keys(key_id,key_hash,name,scopes,created_at) VALUES(?,?,?,?,?)",
                (key_id, self._hash(token), (name or "client")[:80], scope_text, time.time()),
            )
        return key_id, token

    def authenticate(self, token: str) -> ApiPrincipal | None:
        if not token or not token.startswith(PREFIX):
            return None
        digest = self._hash(token)
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT key_id,name,scopes FROM api_keys WHERE key_hash=? AND revoked_at IS NULL",
                (digest,),
            ).fetchone()
            if not row:
                return None
            conn.execute("UPDATE api_keys SET last_used_at=? WHERE key_id=?", (time.time(), row[0]))
        return ApiPrincipal(row[0], row[1], frozenset(x for x in row[2].split(",") if x))

    def revoke(self, key_id: str) -> bool:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "UPDATE api_keys SET revoked_at=? WHERE key_id=? AND revoked_at IS NULL",
                (time.time(), key_id),
            )
            return cur.rowcount == 1

    def list_keys(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT key_id,name,scopes,created_at,last_used_at,revoked_at FROM api_keys ORDER BY created_at DESC"
            ).fetchall()
        return [
            {"key_id": r[0], "name": r[1], "scopes": r[2].split(","), "created_at": r[3], "last_used_at": r[4], "revoked_at": r[5]}
            for r in rows
        ]
