"""Lightweight task router — no LLM, almost zero latency."""
from __future__ import annotations


def route_task(user_text: str) -> str:
    """Return 'tools' or 'chat'.

    tools  → Groq (MCP / image / technical)
    chat   → Gemini (natural conversation, flirty, dirty)
    """
    text = (user_text or "").lower().strip()
    if not text:
        return "chat"

    tool_signals = (
        "image", "photo", "pic", "pics", "dikhao", "dikhhao", "dikha", "dikh",
        "search", "r2", "process", "list", "catalog", "pending", "enhance",
        "code", "error", "debug", "api", "github", "deploy", "docker",
        "file", "video", "audio", "transcript", "voice note",
        "mcp", "vectorize", "object", "key",
    )
    if any(s in text for s in tool_signals):
        return "tools"
    return "chat"
