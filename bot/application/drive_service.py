"""Drive application facade adding semantic ranking without changing the Telegram gateway."""
from __future__ import annotations
from pathlib import Path

from bot.infrastructure.vectorstore.semantic_index import SemanticIndex


class DriveService:
    def __init__(self, client, index: SemanticIndex):
        self.client = client
        self.index = index

    def __getattr__(self, name):
        return getattr(self.client, name)

    def _refresh_root_index(self) -> None:
        try:
            entries = self.client._list_entries(self.client.folder_id)
            for entry in entries.values():
                self.index.upsert(entry.file_id, entry.name)
        except Exception:
            # Search must remain available even when indexing is temporarily unavailable.
            return

    def search(self, query: str) -> str:
        self._refresh_root_index()
        results = self.index.search(query, limit=10)
        if not results or results[0][2] <= 0:
            return self.client.search(query)
        lines = [f"🔍 Semantic search: {query}\n"]
        for key, text, score in results:
            if score <= 0:
                continue
            lines.append(f"• {text}  [match {score:.0%}]")
        return "\n".join(lines) if len(lines) > 1 else self.client.search(query)

    def semantic_download(self, user_id: int, description: str, dest_dir: Path):
        self._refresh_root_index()
        results = self.index.search(description, limit=5)
        for key, text, score in results:
            if score <= 0:
                continue
            dest = dest_dir / Path(text).name
            try:
                self.client.download_to_path(key, dest)
                return "ok", dest.name
            except Exception:
                continue
        return self.client.semantic_download(user_id, description, dest_dir)
