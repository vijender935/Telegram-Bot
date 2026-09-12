#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${MEMORY_DB_PATH:-/var/data/bot_memory.db}"
BACKUP_DIR="${SQLITE_BACKUP_DIR:-$(dirname "$DB_PATH")/backups}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "SQLite database not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="$BACKUP_DIR/bot_memory_${TIMESTAMP}.db"

# SQLite online backup is safer than copying a live database file directly.
python - "$DB_PATH" "$BACKUP_PATH" <<'PY'
import sqlite3
import sys

src_path, dst_path = sys.argv[1:]
src = sqlite3.connect(src_path)
dst = sqlite3.connect(dst_path)
try:
    src.backup(dst)
finally:
    dst.close()
    src.close()
PY

echo "SQLite backup created: $BACKUP_PATH"
