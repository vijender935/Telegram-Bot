"""Lightweight emotion / energy detection from user text (no extra LLM call)."""
from __future__ import annotations

import re

# Hardcoded rules removed. AI now sets emotion via [SET_EMOTION] tag.

def detect_emotion(text: str, current_emotion: str = "neutral") -> str:
    """Fallback to current emotion. AI-driven updates happen in handlers."""
    return current_emotion
