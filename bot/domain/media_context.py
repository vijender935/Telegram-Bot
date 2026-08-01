"""Format media memory for injection into chat prompts."""
from __future__ import annotations


def format_last_media(media: dict | None) -> str:
    if not media:
        return "(no recent media shared)"
    name = media.get("name") or "file"
    kind = media.get("type") or "file"
    desc = (media.get("description") or "").strip()
    reaction = media.get("reaction") or ""
    lines = [f"- Last shared: {name} ({kind})"]
    if desc:
        lines.append(f"- What it shows: {desc}")
    if reaction:
        lines.append(f"- User reaction: {reaction}")
    lines.append("- Talk about this media naturally as if YOU sent it to seduce him.")
    return "\n".join(lines)


def format_session_summary(summary: str | None) -> str:
    s = (summary or "").strip()
    if not s:
        return "(no session summary yet)"
    return s[:800]


def format_active_fantasy(text: str | None) -> str:
    t = (text or "").strip()
    if not t:
        return "(none)"
    return t[:500]
