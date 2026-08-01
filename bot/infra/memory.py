import json
import sqlite3
import threading
from langchain_core.messages import HumanMessage, AIMessage


class MemoryStore:
    """Per-user chat history + mood + profile + session + media + fantasy."""

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
                    name TEXT NOT NULL,
                    type TEXT NOT NULL DEFAULT 'file',
                    description TEXT NOT NULL DEFAULT '',
                    tags TEXT NOT NULL DEFAULT '[]',
                    reaction TEXT NOT NULL DEFAULT '',
                    created_at REAL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_media_user ON media_memory(user_id, created_at DESC)
            """)
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

    # ----- history -----
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

    # ----- mood -----
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

    # ----- profile -----
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

    # ----- session summary -----
    def get_session(self, user_id: int) -> tuple[str, int]:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT summary, msg_count FROM session_summaries WHERE user_id = ?",
                    (user_id,),
                ).fetchone()
        if not row:
            return "", 0
        return row[0] or "", int(row[1] or 0)

    def set_session(self, user_id: int, summary: str, msg_count: int):
        import time
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO session_summaries (user_id, summary, msg_count, updated_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        summary = excluded.summary,
                        msg_count = excluded.msg_count,
                        updated_at = excluded.updated_at
                """, (user_id, summary or "", msg_count, time.time()))

    def bump_session_count(self, user_id: int) -> int:
        summary, count = self.get_session(user_id)
        count += 1
        self.set_session(user_id, summary, count)
        return count

    # ----- emotion -----
    def get_emotion(self, user_id: int) -> str:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT label FROM emotion_state WHERE user_id = ?", (user_id,)
                ).fetchone()
        return row[0] if row else "neutral"

    def set_emotion(self, user_id: int, label: str):
        import time
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO emotion_state (user_id, label, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET label = excluded.label, updated_at = excluded.updated_at
                """, (user_id, label or "neutral", time.time()))

    # ----- media memory -----
    def add_media(
        self,
        user_id: int,
        file_key: str,
        name: str,
        type_: str,
        description: str,
        tags: list | None = None,
    ) -> None:
        import time
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO media_memory
                    (user_id, file_key, name, type, description, tags, reaction, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, '', ?)
                """, (
                    user_id, file_key, name, type_, description or "",
                    json.dumps(tags or [], ensure_ascii=False), time.time(),
                ))

    def get_last_media(self, user_id: int) -> dict | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute("""
                    SELECT file_key, name, type, description, tags, reaction, created_at
                    FROM media_memory WHERE user_id = ?
                    ORDER BY created_at DESC LIMIT 1
                """, (user_id,)).fetchone()
        if not row:
            return None
        return {
            "file_key": row[0],
            "name": row[1],
            "type": row[2],
            "description": row[3],
            "tags": json.loads(row[4] or "[]"),
            "reaction": row[5],
            "created_at": row[6],
        }

    def set_last_media_reaction(self, user_id: int, reaction: str) -> None:
        last = self.get_last_media(user_id)
        if not last:
            return
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    UPDATE media_memory SET reaction = ?
                    WHERE user_id = ? AND file_key = ? AND created_at = ?
                """, (reaction[:200], user_id, last["file_key"], last["created_at"]))

    # ----- active fantasy -----
    def get_fantasy(self, user_id: int) -> str:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT text FROM active_fantasy WHERE user_id = ?", (user_id,)
                ).fetchone()
        return row[0] if row else ""

    def set_fantasy(self, user_id: int, text: str):
        import time
        with self._lock:
            with self._connect() as conn:
                conn.execute("""
                    INSERT INTO active_fantasy (user_id, text, updated_at) VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET text = excluded.text, updated_at = excluded.updated_at
                """, (user_id, text or "", time.time()))

    def clear_fantasy(self, user_id: int):
        with self._lock:
            with self._connect() as conn:
                conn.execute("DELETE FROM active_fantasy WHERE user_id = ?", (user_id,))
