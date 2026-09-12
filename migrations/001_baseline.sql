-- Baseline migration marker for the SQLite schema already created by MemoryStore.
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY, applied_at REAL NOT NULL);
INSERT OR IGNORE INTO schema_version(version, applied_at) VALUES (1, strftime('%s','now'));
