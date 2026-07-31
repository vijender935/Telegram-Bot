import sqlite3
import json
import threading
from langchain_core.messages import HumanMessage, AIMessage


class MemoryStore:
<<<<<<< HEAD
    """SQLite-backed persistent chat history per user."""
=======
    """SQLite-backed persistent chat history + moods per user."""
>>>>>>> 5336183 (Adding Transcript)

    def __init__(self, db_path: str = "/tmp/bot_memory.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    user_id INTEGER PRIMARY KEY,
                    history TEXT NOT NULL DEFAULT '[]'
                )
            """)
<<<<<<< HEAD
=======
            conn.execute("""
                CREATE TABLE IF NOT EXISTS moods (
                    user_id INTEGER PRIMARY KEY,
                    mood TEXT NOT NULL DEFAULT 'Horny / Flirty'
                )
            """)
>>>>>>> 5336183 (Adding Transcript)

    def _connect(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def get(self, user_id: int) -> list:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT history FROM memories WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
        if not row:
            return []
        raw = json.loads(row[0])
        messages = []
        for m in raw:
            if m["type"] == "human":
                messages.append(HumanMessage(content=m["content"]))
            elif m["type"] == "ai":
                messages.append(AIMessage(content=m["content"]))
        return messages

    def save(self, user_id: int, history: list, max_messages: int = 20):
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
                    INSERT INTO memories (user_id, history)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET history = excluded.history
                """, (user_id, json.dumps(raw)))

    def clear(self, user_id: int):
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM memories WHERE user_id = ?",
                    (user_id,)
<<<<<<< HEAD
                )
=======
                )

    # ── Mood methods ──────────────────────────────────────────
    def get_mood(self, user_id: int) -> str:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT mood FROM moods WHERE user_id = ?",
                    (user_id,)
                ).fetchone()
        return row[0] if row else "Horny / Flirty"

    def set_mood(self, user_id: int, mood: str):
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO moods (user_id, mood)
                    VALUES (?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET mood = excluded.mood
                """, (user_id, mood))
>>>>>>> 5336183 (Adding Transcript)
