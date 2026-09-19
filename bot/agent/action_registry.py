"""Validated internal Action-Tag compatibility layer.

The Cloudflare image/data path uses native MCP tool calls. Tags remain only for
existing local features that are not part of the remote image/data layer.
"""
from __future__ import annotations

ALLOWED_ACTIONS = {
    "VOICE", "VAULT_ADD", "VAULT_LIST", "VAULT_OPEN", "SET_EMOTION", "EVOLVE",
}


def parse_action_tags(text: str) -> tuple[str, list[tuple[str, str | None]]]:
    import re

    actions: list[tuple[str, str | None]] = []
    pattern = r"\[([A-Z_]+)(?::\s*([^\]]+))?\]"
    for match in re.finditer(pattern, text or ""):
        tag, value = match.group(1), match.group(2)
        if tag in ALLOWED_ACTIONS:
            actions.append((tag, value.strip() if value else None))
    clean = re.sub(pattern, "", text or "").strip()
    return clean, actions
