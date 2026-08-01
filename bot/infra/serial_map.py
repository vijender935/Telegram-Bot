import json
import time
import threading
from dataclasses import dataclass, field
from pathlib import Path


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
    """User-scoped serial → file map with TTL. Optional SQLite persistence via path."""

    def __init__(self, ttl_seconds: int = 1800, db_path: str | None = None):
        self.ttl = ttl_seconds
        self._data: dict[int, UserList] = {}
        self._lock = threading.Lock()
        self.db_path = db_path
        if db_path:
            self._init_db()
            self._load_all()

    def _init_db(self):
        import sqlite3
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS serial_maps (
                    user_id INTEGER PRIMARY KEY,
                    entries TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
            """)

    def _load_all(self):
        import sqlite3
        try:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("SELECT user_id, entries, created_at FROM serial_maps").fetchall()
            now = time.time()
            for uid, entries_json, created_at in rows:
                if now - created_at > self.ttl:
                    continue
                raw = json.loads(entries_json)
                entries = {
                    int(k): FileEntry(file_id=v["file_id"], name=v["name"], mime=v.get("mime", ""))
                    for k, v in raw.items()
                }
                self._data[int(uid)] = UserList(entries=entries, created_at=created_at)
        except Exception:
            pass

    def _persist(self, user_id: int, ul: UserList | None):
        if not self.db_path:
            return
        import sqlite3
        try:
            with sqlite3.connect(self.db_path) as conn:
                if ul is None:
                    conn.execute("DELETE FROM serial_maps WHERE user_id = ?", (user_id,))
                    return
                raw = {
                    str(k): {"file_id": v.file_id, "name": v.name, "mime": v.mime}
                    for k, v in ul.entries.items()
                }
                conn.execute("""
                    INSERT INTO serial_maps (user_id, entries, created_at) VALUES (?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET entries = excluded.entries, created_at = excluded.created_at
                """, (user_id, json.dumps(raw, ensure_ascii=False), ul.created_at))
        except Exception:
            pass

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
