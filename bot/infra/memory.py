import json
import sqlite3
import threading
from langchain_core.messages import HumanMessage, AIMessage


class MemoryStore:
    """Per-user chat history + mood + learned profile (SQLite)."""

    def __init__(self, db_path: str = "/tmp/bot_memory.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    user_id INTEGER PRIMARY KEY,
                    history TEXT NOT NULL DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS moods (
                    user_id INTEGER PRIMARY KEY,
                    mood TEXT NOT NULL DEFAULT 'Horny / Flirty'
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    profile TEXT NOT NULL DEFAULT '{}'
                )
            """)

    def get_history(self, user_id: int) -> list:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT history FROM memories WHERE user_id = ?", (user_id,)
                ).fetchone()
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
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO memories (user_id, history) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET history = excluded.history
                """, (user_id, json.dumps(raw, ensure_ascii=False)))

    def clear_history(self, user_id: int):
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM memories WHERE user_id = ?", (user_id,))

    def get_mood(self, user_id: int) -> str:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT mood FROM moods WHERE user_id = ?", (user_id,)
                ).fetchone()
        return row[0] if row else "Horny / Flirty"

    def set_mood(self, user_id: int, mood: str):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO moods (user_id, mood) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET mood = excluded.mood
                """, (user_id, mood))

    def get_profile(self, user_id: int) -> dict:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT profile FROM profiles WHERE user_id = ?", (user_id,)
                ).fetchone()
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    def set_profile(self, user_id: int, profile: dict):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO profiles (user_id, profile) VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET profile = excluded.profile
                """, (user_id, json.dumps(profile or {}, ensure_ascii=False)))

    def clear_profile(self, user_id: int):
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
