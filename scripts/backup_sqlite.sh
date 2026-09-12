#!/usr/bin/env bash
set -euo pipefail

DB_PATH="${MEMORY_DB_PATH:-/var/data/bot_memory.db}"
BACKUP_DIR="${SQLITE_BACKUP_DIR:-$(dirname "$DB_PATH")/backups}"
RETENTION_DAYS="${SQLITE_BACKUP_RETENTION_DAYS:-14}"

if [[ ! -f "$DB_PATH" ]]; then
  echo "SQLite database not found: $DB_PATH" >&2
  exit 1
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="$BACKUP_DIR/bot_memory_${TIMESTAMP}.db"

python - "$DB_PATH" "$BACKUP_PATH" <<'PY'
import sqlite3, sys
src_path, dst_path = sys.argv[1:]
src = sqlite3.connect(src_path)
dst = sqlite3.connect(dst_path)
try:
    src.backup(dst)
    result = dst.execute("PRAGMA integrity_check").fetchone()[0]
    if result != "ok":
        raise SystemExit(f"Backup integrity check failed: {result}")
finally:
    dst.close(); src.close()
PY

find "$BACKUP_DIR" -type f -name 'bot_memory_*.db' -mtime +"$RETENTION_DAYS" -delete
echo "SQLite backup created and verified: $BACKUP_PATH"
