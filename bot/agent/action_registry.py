"""Deprecated compatibility shim.

The bot is prompt-first and no longer uses hard-coded action tags.
"""
from __future__ import annotations


def parse_action_tags(text: str) -> tuple[str, list[tuple[str, str | None]]]:
    return (text or "").strip(), []
