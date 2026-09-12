import json
import time
import threading
import os
import hashlib
import sqlite3
from langchain_core.messages import HumanMessage, AIMessage


class MemoryStore:
    """Persistent per-user memory backed by a local SQLite database."""

    def __init__(self, db_path: str = "memory.db"):
        self._lock = threading.Lock()
        self._mode = "sqlite"
        self._db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _conn(self):
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _put(self, conn):
        conn.close()

    def _init_db(self):
        conn = self._conn()
        try:
            with conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        user_id INTEGER PRIMARY KEY,
                        history TEXT NOT NULL DEFAULT '[]'
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS moods (
                        user_id INTEGER PRIMARY KEY,
                        mood TEXT NOT NULL DEFAULT 'Strapon / Pegging'
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS profiles (
                        user_id INTEGER PRIMARY KEY,
                        profile TEXT NOT NULL DEFAULT '{}'
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS session_summaries (
                        user_id INTEGER PRIMARY KEY,
                        summary TEXT NOT NULL DEFAULT '',
                        msg_count INTEGER NOT NULL DEFAULT 0,
                        updated_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS emotion_state (
                        user_id INTEGER PRIMARY KEY,
                        label TEXT NOT NULL DEFAULT 'neutral',
                        updated_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS media_memory (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        file_key TEXT NOT NULL,
                        file_id TEXT,
                        name TEXT NOT NULL,
                        type TEXT NOT NULL DEFAULT 'file',
                        description TEXT NOT NULL DEFAULT '',
                        tags TEXT NOT NULL DEFAULT '[]',
                        reaction TEXT NOT NULL DEFAULT '',
                        created_at REAL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_media_user ON media_memory(user_id, created_at DESC)")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS active_fantasy (
                        user_id INTEGER PRIMARY KEY,
                        text TEXT NOT NULL DEFAULT '',
                        updated_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS serial_maps (
                        user_id INTEGER PRIMARY KEY,
                        entries TEXT NOT NULL DEFAULT '{}',
                        created_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vault_codes (
                        user_id INTEGER PRIMARY KEY,
                        code TEXT NOT NULL,
                        updated_at REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vault_entries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        file_id TEXT NOT NULL,
                        file_name TEXT,
                        label TEXT,
                        description TEXT,
                        created_at REAL
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_vault_user ON vault_entries(user_id, created_at DESC)")
        finally:
            self._put(conn)

    def _execute(self, query: str, params: tuple = (), fetch: str = "none"):
        query = query.replace("%s", "?")
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute(query, params)
                if fetch == "one":
                    return cur.fetchone()
                if fetch == "all":
                    return cur.fetchall()
        finally:
            self._put(conn)

    def get_history(self, user_id: int) -> list:
        row = self._execute("SELECT history FROM memories WHERE user_id = %s", (user_id,), fetch="one")
        if not row:
            return []
        messages = []
        for m in json.loads(row[0]):
            if m["type"] == "human":
                messages.append(HumanMessage(content=m["content"]))
            elif m["type"] == "ai":
                messages.append(AIMessage(content=m["content"]))
        return messages

    def save_history(self, user_id: int, history: list, max_messages: int = 20):
        history = history[-max_messages:]
        raw = []
        for m in history:
            if isinstance(m, HumanMessage):
                raw.append({"type": "human", "content": m.content})
            elif isinstance(m, AIMessage):
                raw.append({"type": "ai", "content": m.content})
        self._execute(
            "INSERT INTO memories (user_id, history) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET history = excluded.history",
            (user_id, json.dumps(raw, ensure_ascii=False)),
        )

    def clear_history(self, user_id: int):
        self._execute("DELETE FROM memories WHERE user_id = %s", (user_id,))

    def get_mood(self, user_id: int) -> str:
        row = self._execute("SELECT mood FROM moods WHERE user_id = %s", (user_id,), fetch="one")
        return row[0] if row else "Strapon / Pegging"

    def set_mood(self, user_id: int, mood: str):
        self._execute(
            "INSERT INTO moods (user_id, mood) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET mood = excluded.mood",
            (user_id, mood),
        )

    def get_profile(self, user_id: int) -> dict:
        row = self._execute("SELECT profile FROM profiles WHERE user_id = %s", (user_id,), fetch="one")
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    def set_profile(self, user_id: int, profile: dict):
        self._execute(
            "INSERT INTO profiles (user_id, profile) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET profile = excluded.profile",
            (user_id, json.dumps(profile or {}, ensure_ascii=False)),
        )

    def clear_profile(self, user_id: int):
        self._execute("DELETE FROM profiles WHERE user_id = %s", (user_id,))

    def clear_all_for_user(self, user_id: int):
        tables = ["memories", "profiles", "moods", "emotion_state", "session_summaries", "active_fantasy", "media_memory", "serial_maps", "vault_codes", "vault_entries"]
        for table in tables:
            self._execute(f"DELETE FROM {table} WHERE user_id = %s", (user_id,))

    def get_session(self, user_id: int) -> tuple[str, int]:
        row = self._execute("SELECT summary, msg_count FROM session_summaries WHERE user_id = %s", (user_id,), fetch="one")
        if not row:
            return "", 0
        return row[0] or "", int(row[1] or 0)

    def set_session(self, user_id: int, summary: str, msg_count: int):
        self._execute(
            "INSERT INTO session_summaries (user_id, summary, msg_count, updated_at) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET summary = excluded.summary, msg_count = excluded.msg_count, updated_at = excluded.updated_at",
            (user_id, summary or "", msg_count, time.time()),
        )

    def bump_session_count(self, user_id: int) -> int:
        summary, count = self.get_session(user_id)
        count += 1
        self.set_session(user_id, summary, count)
        return count

    def get_emotion(self, user_id: int) -> str:
        row = self._execute("SELECT label FROM emotion_state WHERE user_id = %s", (user_id,), fetch="one")
        return row[0] if row else "neutral"

    def set_emotion(self, user_id: int, label: str):
        self._execute(
            "INSERT INTO emotion_state (user_id, label, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET label = excluded.label, updated_at = excluded.updated_at",
            (user_id, label or "neutral", time.time()),
        )

    def add_media(self, user_id: int, file_key: str, name: str, type_: str, description: str, tags: list | None = None, file_id: str | None = None) -> None:
        self._execute(
            "INSERT INTO media_memory (user_id, file_key, file_id, name, type, description, tags, reaction, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?)",
            (user_id, file_key, file_id, name, type_, description or "", json.dumps(tags or [], ensure_ascii=False), time.time()),
        )

    def get_last_media(self, user_id: int) -> dict | None:
        row = self._execute("SELECT file_key, file_id, name, type, description, tags, reaction, created_at FROM media_memory WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user_id,), fetch="one")
        if not row:
            return None
        return {"file_key": row[0], "file_id": row[1], "name": row[2], "type": row[3], "description": row[4], "tags": json.loads(row[5] or "[]"), "reaction": row[6], "created_at": row[7]}

    def set_last_media_reaction(self, user_id: int, reaction: str) -> None:
        last = self.get_last_media(user_id)
        if not last:
            return
        self._execute("UPDATE media_memory SET reaction = %s WHERE user_id = %s AND file_key = %s AND created_at = %s", (reaction[:200], user_id, last["file_key"], last["created_at"]))

    def get_fantasy(self, user_id: int) -> str:
        row = self._execute("SELECT text FROM active_fantasy WHERE user_id = %s", (user_id,), fetch="one")
        return row[0] if row else ""

    def set_fantasy(self, user_id: int, text: str):
        self._execute(
            "INSERT INTO active_fantasy (user_id, text, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at",
            (user_id, text or "", time.time()),
        )

    def get_serial_map(self, user_id: int) -> dict:
        row = self._execute("SELECT entries FROM serial_maps WHERE user_id = %s", (user_id,), fetch="one")
        if not row:
            return {}
        return json.loads(row[0])

    def set_serial_map(self, user_id: int, entries: dict):
        self._execute(
            "INSERT INTO serial_maps (user_id, entries, created_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET entries = excluded.entries, created_at = excluded.created_at",
            (user_id, json.dumps(entries), time.time()),
        )

    def _hash_code(self, code: str) -> str:
        return hashlib.sha256(code.encode()).hexdigest()

    def get_vault_code(self, user_id: int) -> str | None:
        row = self._execute("SELECT code FROM vault_codes WHERE user_id = %s", (user_id,), fetch="one")
        return row[0] if row else None

    def verify_vault_code(self, user_id: int, code: str) -> bool:
        saved = self.get_vault_code(user_id)
        return bool(saved and saved == self._hash_code(code))

    def set_vault_code(self, user_id: int, code: str):
        self._execute(
            "INSERT INTO vault_codes (user_id, code, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET code = excluded.code, updated_at = excluded.updated_at",
            (user_id, self._hash_code(code), time.time()),
        )

    def add_vault_entry(self, user_id: int, file_id: str, file_name: str, label: str, description: str = ""):
        self._execute("INSERT INTO vault_entries (user_id, file_id, file_name, label, description, created_at) VALUES (?, ?, ?, ?, ?, ?)", (user_id, file_id, file_name, label, description, time.time()))

    def get_vault_entries(self, user_id: int) -> list:
        rows = self._execute("SELECT id, file_id, file_name, label, description, created_at FROM vault_entries WHERE user_id = %s ORDER BY created_at DESC", (user_id,), fetch="all") or []
        return [{"id": r[0], "file_id": r[1], "file_name": r[2], "label": r[3], "description": r[4], "created_at": r[5]} for r in rows]

    def delete_vault_entry(self, user_id: int, entry_id: int):
        self._execute("DELETE FROM vault_entries WHERE user_id = %s AND id = %s", (user_id, entry_id))

    def get_all_user_ids(self) -> list[int]:
        rows = self._execute("SELECT DISTINCT user_id FROM memories", fetch="all")
        return [row[0] for row in rows] if rows else []
