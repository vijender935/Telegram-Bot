"""Runtime tool factory for structured agent calls.

Tools are created per user so authorization/context is never supplied by the model.
"""
from __future__ import annotations

from langchain_core.tools import tool


def build_tools(memory=None, drive=None, user_id: int | None = None, sandbox_path: str | None = None) -> list:
    tools = []

    if memory is not None and user_id is not None:
        @tool
        def memory_search(query: str) -> str:
            """Search the user's saved semantic memories."""
            results = memory.search(query, limit=5)
            if not results:
                return "No matching memories."
            return "\n".join(f"{text} (score={score:.0%})" for _, text, score in results)
        tools.append(memory_search)

    if drive is not None and user_id is not None:
        @tool
        def drive_search(query: str) -> str:
            """Search the user's configured Google Drive using semantic ranking."""
            return drive.search(query)
        tools.append(drive_search)

    return tools
