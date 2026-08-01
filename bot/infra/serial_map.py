import time
import threading
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
    """User-scoped serial → file map with TTL."""

    def __init__(self, ttl_seconds: int = 1800):
        self.ttl = ttl_seconds
        self._data: dict[int, UserList] = {}
        self._lock = threading.Lock()

    def set_list(self, user_id: int, entries: dict[int, FileEntry]):
        with self._lock:
            self._data[user_id] = UserList(entries=entries, created_at=time.time())

    def get(self, user_id: int, serial: int) -> FileEntry | None:
        with self._lock:
            ul = self._data.get(user_id)
            if not ul:
                return None
            if time.time() - ul.created_at > self.ttl:
                del self._data[user_id]
                return None
            return ul.entries.get(int(serial))

    def clear(self, user_id: int):
        with self._lock:
            self._data.pop(user_id, None)
