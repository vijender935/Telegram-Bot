"""Lightweight persistent semantic index with optional scoped retrieval."""
from __future__ import annotations

import json
import math
import os
import re
import sqlite3
from pathlib import Path


class SemanticIndex:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.enabled = os.getenv("SEMANTIC_EMBEDDINGS", "false").lower() in {"1", "true", "yes"}
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS semantic_index (key TEXT PRIMARY KEY, text TEXT NOT NULL, vector TEXT)"
            )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        return {x for x in re.findall(r"[\w-]+", (text or "").lower()) if len(x) > 1}

    def _embed(self, text: str):
        if not self.enabled:
            return None
        try:
            from sentence_transformers import SentenceTransformer
            if not hasattr(self, "_model"):
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
            return self._model.encode([text], normalize_embeddings=True)[0].tolist()
        except Exception:
            return None

    def upsert(self, key: str, text: str) -> None:
        text = (text or "").strip()
        if not key or not text:
            return
        vector = self._embed(text)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO semantic_index(key,text,vector) VALUES(?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET text=excluded.text, vector=excluded.vector",
                (key, text, json.dumps(vector) if vector else None),
            )

    def delete_prefix(self, prefix: str) -> None:
        if not prefix:
            return
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM semantic_index WHERE key LIKE ?", (prefix + "%",))

    def search(self, query: str, limit: int = 10, prefix: str | None = None) -> list[tuple[str, str, float]]:
        query = (query or "").strip()
        if not query:
            return []
        qv = self._embed(query)
        with sqlite3.connect(self.db_path) as conn:
            if prefix is None:
                rows = conn.execute("SELECT key,text,vector FROM semantic_index").fetchall()
            else:
                rows = conn.execute(
                    "SELECT key,text,vector FROM semantic_index WHERE key LIKE ?",
                    (prefix + "%",),
                ).fetchall()
        if qv:
            def cosine(raw):
                if not raw:
                    return 0.0
                try:
                    v = json.loads(raw)
                except (TypeError, json.JSONDecodeError):
                    return 0.0
                denom = max(1e-9, math.sqrt(sum(a * a for a in qv)) * math.sqrt(sum(b * b for b in v)))
                return sum(a * b for a, b in zip(qv, v)) / denom
            ranked = [(k, t, cosine(v)) for k, t, v in rows]
        else:
            qt = self._tokens(query)
            ranked = [(k, t, len(qt & self._tokens(t)) / max(1, len(qt))) for k, t, _ in rows]
        ranked = [item for item in ranked if item[2] > 0.0]
        return sorted(ranked, key=lambda x: x[2], reverse=True)[: max(1, limit)]
