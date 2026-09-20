"""Lightweight persistent lexical index for private conversation memory.

Image semantic retrieval is handled by the user's Cloudflare Vectorize layer.
The bot keeps its private conversational-memory index dependency-free so the
Render service does not need PyTorch/CUDA just to start.
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from pathlib import Path


class SemanticIndex:
    """SQLite-backed scoped text index with deterministic token similarity."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS semantic_index "
                "(key TEXT PRIMARY KEY, text TEXT NOT NULL, vector TEXT)"
            )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[\w-]+", (text or "").lower())
            if len(token) > 1
        }

    def upsert(self, key: str, text: str) -> None:
        text = (text or "").strip()
        if not key or not text:
            return
        tokens = sorted(self._tokens(text))
        vector = {token: tokens.count(token) for token in tokens}
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO semantic_index(key,text,vector) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET text=excluded.text, vector=excluded.vector",
                (key, text, json.dumps(vector, ensure_ascii=False)),
            )

    def delete_prefix(self, prefix: str) -> None:
        if not prefix:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM semantic_index WHERE key LIKE ?",
                (prefix + "%",),
            )

    def search(
        self, query: str, limit: int = 10, prefix: str | None = None
    ) -> list[tuple[str, str, float]]:
        query = (query or "").strip()
        if not query:
            return []

        qt = self._tokens(query)
        if not qt:
            return []

        with sqlite3.connect(self.db_path) as conn:
            if prefix is None:
                rows = conn.execute(
                    "SELECT key,text,vector FROM semantic_index"
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key,text,vector FROM semantic_index WHERE key LIKE ?",
                    (prefix + "%",),
                ).fetchall()

        qnorm = math.sqrt(len(qt))
        ranked: list[tuple[str, str, float]] = []
        for key, text, raw_vector in rows:
            try:
                vector = json.loads(raw_vector or "{}")
            except (TypeError, json.JSONDecodeError):
                vector = {}
            if not vector:
                continue
            overlap = sum(1 for token in qt if token in vector)
            score = overlap / max(1.0, qnorm * math.sqrt(len(vector)))
            if score > 0:
                ranked.append((key, text, min(1.0, score)))

        return sorted(ranked, key=lambda item: item[2], reverse=True)[: max(1, limit)]
