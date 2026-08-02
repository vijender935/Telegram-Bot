import json
import time
import threading
import os
import psycopg2
import psycopg2.pool
from langchain_core.messages import HumanMessage, AIMessage


def _get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        raise RuntimeError("DATABASE_URL environment variable not set!")
    # Render gives 'postgres://' but psycopg2 needs 'postgresql://'
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    return dsn


class MemoryStore:
    """Per-user chat history + mood + profile + session + media + fantasy — Postgres backend."""

    def __init__(self, db_path: str = None):
        # db_path ignored (SQLite legacy param), Postgres uses DATABASE_URL
        self._lock = threading.Lock()
        self._pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=_get_dsn(),
        )
        self._init_db()

    def _conn(self):
        return self._pool.getconn()

    def _put(self, conn):
        self._pool.putconn(conn)

    def _init_db(self):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS memories (
                        user_id BIGINT PRIMARY KEY,
                        history TEXT NOT NULL DEFAULT '[]'
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS moods (
                        user_id BIGINT PRIMARY KEY,
                        mood TEXT NOT NULL DEFAULT 'Horny / Flirty'
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS profiles (
                        user_id BIGINT PRIMARY KEY,
                        profile TEXT NOT NULL DEFAULT '{}'
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS session_summaries (
                        user_id BIGINT PRIMARY KEY,
                        summary TEXT NOT NULL DEFAULT '',
                        msg_count INTEGER NOT NULL DEFAULT 0,
                        updated_at DOUBLE PRECISION
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS emotion_state (
                        user_id BIGINT PRIMARY KEY,
                        label TEXT NOT NULL DEFAULT 'neutral',
                        updated_at DOUBLE PRECISION
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS media_memory (
                        id SERIAL PRIMARY KEY,
                        user_id BIGINT NOT NULL,
                        file_key TEXT NOT NULL,
                        name TEXT NOT NULL,
                        type TEXT NOT NULL DEFAULT 'file',
                        description TEXT NOT NULL DEFAULT '',
                        tags TEXT NOT NULL DEFAULT '[]',
                        reaction TEXT NOT NULL DEFAULT '',
                        created_at DOUBLE PRECISION
                    )
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_media_user
                    ON media_memory(user_id, created_at DESC)
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS active_fantasy (
                        user_id BIGINT PRIMARY KEY,
                        text TEXT NOT NULL DEFAULT '',
                        updated_at DOUBLE PRECISION
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS serial_maps (
                        user_id BIGINT PRIMARY KEY,
                        entries TEXT NOT NULL DEFAULT '{}',
                        created_at DOUBLE PRECISION
                    )
                """)
            conn.commit()
        finally:
            self._put(conn)

    # ───────────── history ─────────────
    def get_history(self, user_id: int) -> list:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT history FROM memories WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
        finally:
            self._put(conn)
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
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO memories (user_id, history) VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET history = EXCLUDED.history
                """, (user_id, json.dumps(raw, ensure_ascii=False)))
            conn.commit()
        finally:
            self._put(conn)

    def clear_history(self, user_id: int):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM memories WHERE user_id = %s", (user_id,))
            conn.commit()
        finally:
            self._put(conn)

    # ───────────── mood ─────────────
    def get_mood(self, user_id: int) -> str:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT mood FROM moods WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
        finally:
            self._put(conn)
        return row[0] if row else "Horny / Flirty"

    def set_mood(self, user_id: int, mood: str):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO moods (user_id, mood) VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET mood = EXCLUDED.mood
                """, (user_id, mood))
            conn.commit()
        finally:
            self._put(conn)

    # ───────────── profile ─────────────
    def get_profile(self, user_id: int) -> dict:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT profile FROM profiles WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
        finally:
            self._put(conn)
        if not row or not row[0]:
            return {}
        try:
            return json.loads(row[0])
        except Exception:
            return {}

    def set_profile(self, user_id: int, profile: dict):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO profiles (user_id, profile) VALUES (%s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET profile = EXCLUDED.profile
                """, (user_id, json.dumps(profile or {}, ensure_ascii=False)))
            conn.commit()
        finally:
            self._put(conn)

    def clear_profile(self, user_id: int):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM profiles WHERE user_id = %s", (user_id,))
            conn.commit()
        finally:
            self._put(conn)

    # ───────────── session summary ─────────────
    def get_session(self, user_id: int) -> tuple[str, int]:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT summary, msg_count FROM session_summaries WHERE user_id = %s",
                    (user_id,)
                )
                row = cur.fetchone()
        finally:
            self._put(conn)
        if not row:
            return "", 0
        return row[0] or "", int(row[1] or 0)

    def set_session(self, user_id: int, summary: str, msg_count: int):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO session_summaries (user_id, summary, msg_count, updated_at)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        summary = EXCLUDED.summary,
                        msg_count = EXCLUDED.msg_count,
                        updated_at = EXCLUDED.updated_at
                """, (user_id, summary or "", msg_count, time.time()))
            conn.commit()
        finally:
            self._put(conn)

    def bump_session_count(self, user_id: int) -> int:
        summary, count = self.get_session(user_id)
        count += 1
        self.set_session(user_id, summary, count)
        return count

    # ───────────── emotion ─────────────
    def get_emotion(self, user_id: int) -> str:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT label FROM emotion_state WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
        finally:
            self._put(conn)
        return row[0] if row else "neutral"

    def set_emotion(self, user_id: int, label: str):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO emotion_state (user_id, label, updated_at) VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        label = EXCLUDED.label,
                        updated_at = EXCLUDED.updated_at
                """, (user_id, label or "neutral", time.time()))
            conn.commit()
        finally:
            self._put(conn)

    # ───────────── media memory ─────────────
    def add_media(self, user_id: int, file_key: str, name: str,
                  type_: str, description: str, tags: list | None = None) -> None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO media_memory
                    (user_id, file_key, name, type, description, tags, reaction, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, '', %s)
                """, (
                    user_id, file_key, name, type_, description or "",
                    json.dumps(tags or [], ensure_ascii=False), time.time(),
                ))
            conn.commit()
        finally:
            self._put(conn)

    def get_last_media(self, user_id: int) -> dict | None:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT file_key, name, type, description, tags, reaction, created_at
                    FROM media_memory WHERE user_id = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (user_id,))
                row = cur.fetchone()
        finally:
            self._put(conn)
        if not row:
            return None
        return {
            "file_key": row[0], "name": row[1], "type": row[2],
            "description": row[3], "tags": json.loads(row[4] or "[]"),
            "reaction": row[5], "created_at": row[6],
        }

    def set_last_media_reaction(self, user_id: int, reaction: str) -> None:
        last = self.get_last_media(user_id)
        if not last:
            return
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE media_memory SET reaction = %s
                    WHERE user_id = %s AND file_key = %s AND created_at = %s
                """, (reaction[:200], user_id, last["file_key"], last["created_at"]))
            conn.commit()
        finally:
            self._put(conn)

    # ───────────── active fantasy ─────────────
    def get_fantasy(self, user_id: int) -> str:
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT text FROM active_fantasy WHERE user_id = %s", (user_id,))
                row = cur.fetchone()
        finally:
            self._put(conn)
        return row[0] if row else ""

    def set_fantasy(self, user_id: int, text: str):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO active_fantasy (user_id, text, updated_at) VALUES (%s, %s, %s)
                    ON CONFLICT (user_id) DO UPDATE SET
                        text = EXCLUDED.text,
                        updated_at = EXCLUDED.updated_at
                """, (user_id, text or "", time.time()))
            conn.commit()
        finally:
            self._put(conn)

    def clear_fantasy(self, user_id: int):
        conn = self._conn()
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM active_fantasy WHERE user_id = %s", (user_id,))
            conn.commit()
        finally:
            self._put(conn)
