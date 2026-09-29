import json
import time
import threading
import sqlite3
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


class SerialMapStore:
    """User-scoped serial → file map with TTL, persisted in SQLite."""

    def __init__(self, ttl_seconds: int = 1800, db_path: str = "memory.db"):
        self.ttl = ttl_seconds
        self._db_path = db_path
        self._data: dict[int, UserList] = {}
        self._lock = threading.Lock()
        self._init_db()
        self._load_all()

    def _connect(self):
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS serial_maps (
                    user_id INTEGER PRIMARY KEY,
                    entries TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL
                )
            """)
            conn.commit()

    def _load_all(self):
        now = time.time()
        with self._connect() as conn:
            rows = conn.execute("SELECT user_id, entries, created_at FROM serial_maps").fetchall()
        for row in rows:
            if now - row["created_at"] > self.ttl:
                continue
            raw = json.loads(row["entries"])
            entries = {
                int(k): FileEntry(file_id=v["file_id"], name=v["name"], mime=v.get("mime", ""))
                for k, v in raw.items()
            }
            self._data[int(row["user_id"])] = UserList(entries=entries, created_at=row["created_at"])

    def _persist(self, user_id: int, ul: UserList | None):
        with self._connect() as conn:
            if ul is None:
                conn.execute("DELETE FROM serial_maps WHERE user_id = ?", (user_id,))
            else:
                raw = {str(k): {"file_id": v.file_id, "name": v.name, "mime": v.mime} for k, v in ul.entries.items()}
                conn.execute("""
                    INSERT INTO serial_maps (user_id, entries, created_at) VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET entries=excluded.entries, created_at=excluded.created_at
                """, (user_id, json.dumps(raw, ensure_ascii=False), ul.created_at))
            conn.commit()

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
