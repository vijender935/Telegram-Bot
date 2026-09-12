"""Idempotent SQLite migration runner.

Usage: python scripts/migrate_sqlite.py /var/data/bot_memory.db
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path


def main() -> None:
    db = Path(sys.argv[1] if len(sys.argv) > 1 else "bot_memory.db")
    migrations = sorted(Path(__file__).resolve().parents[1].joinpath("migrations").glob("*.sql"))
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at REAL NOT NULL)")
        current = conn.execute("SELECT COALESCE(MAX(version), 0) FROM schema_version").fetchone()[0]
        for path in migrations:
            version = int(path.stem.split("_", 1)[0])
            if version <= current:
                continue
            conn.executescript(path.read_text(encoding="utf-8"))
            print(f"Applied migration {version}: {path.name}")


if __name__ == "__main__":
    main()
