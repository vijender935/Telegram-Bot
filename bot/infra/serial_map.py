import json
import time
import threading
import os
import psycopg2
from dataclasses import dataclass, field


@dataclass
class FileEntry:
    file_id: str
    name: str
    mime: str


@dataclass
class UserList:
    entries: dict[int, FileEntry] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


def _get_dsn() -> str:
    dsn = os.getenv("DATABASE_URL", "")
    if dsn.startswith("postgres://"):
        dsn = "postgresql://" + dsn[len("postgres://"):]
    return dsn


class SerialMapStore:
    """User-scoped serial → file map with TTL — Postgres backend."""

    def __init__(self, ttl_seconds: int = 1800, db_path: str | None = None):
        # db_path ignored — Postgres use hota hai
        self.ttl = ttl_seconds
        self._data: dict[int, UserList] = {}
        self._lock = threading.Lock()
        self._dsn = _get_dsn()
        if self._dsn:
            self._init_db()
            self._load_all()

    def _connect(self):
        return psycopg2.connect(self._dsn)

    def _init_db(self):
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS serial_maps (
                            user_id BIGINT PRIMARY KEY,
                            entries TEXT NOT NULL DEFAULT '{}',
                            created_at DOUBLE PRECISION NOT NULL
                        )
                    """)
                conn.commit()
        except Exception as e:
            print(f"SerialMapStore init warning: {e}")

    def _load_all(self):
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT user_id, entries, created_at FROM serial_maps")
                    rows = cur.fetchall()
            now = time.time()
            for uid, entries_json, created_at in rows:
                if now - created_at > self.ttl:
                    continue
                raw = json.loads(entries_json)
                entries = {
                    int(k): FileEntry(
                        file_id=v["file_id"], name=v["name"], mime=v.get("mime", "")
                    )
                    for k, v in raw.items()
                }
                self._data[int(uid)] = UserList(entries=entries, created_at=created_at)
        except Exception as e:
            print(f"SerialMapStore load warning: {e}")

    def _persist(self, user_id: int, ul: UserList | None):
        if not self._dsn:
            return
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    if ul is None:
                        cur.execute("DELETE FROM serial_maps WHERE user_id = %s", (user_id,))
                    else:
                        raw = {
                            str(k): {"file_id": v.file_id, "name": v.name, "mime": v.mime}
                            for k, v in ul.entries.items()
                        }
                        cur.execute("""
                            INSERT INTO serial_maps (user_id, entries, created_at)
                            VALUES (%s, %s, %s)
                            ON CONFLICT (user_id) DO UPDATE SET
                                entries = EXCLUDED.entries,
                                created_at = EXCLUDED.created_at
                        """, (user_id, json.dumps(raw, ensure_ascii=False), ul.created_at))
                conn.commit()
        except Exception as e:
            print(f"SerialMapStore persist warning: {e}")

    def set_list(self, user_id: int, entries: dict[int, FileEntry]):
        ul = UserList(entries=entries, created_at=time.time())
        with self._lock:
            self._data[user_id] = ul
            self._persist(user_id, ul)

    def get(self, user_id: int, serial: int) -> FileEntry | None:
        with self._lock:
            ul = self._data.get(user_id)
            if not ul:
                return None
            if time.time() - ul.created_at > self.ttl:
                del self._data[user_id]
                self._persist(user_id, None)
                return None
            return ul.entries.get(int(serial))

    def clear(self, user_id: int):
        with self._lock:
            self._data.pop(user_id, None)
            self._persist(user_id, None)
