"""Lightweight task router with intent-aware, deterministic classification."""
from __future__ import annotations

import re


# These are semantic intent groups rather than a flat keyword switch.
# The router only makes the high-level model decision; Groq still owns
# MCP/tool selection after a request enters the tools path.
_MEDIA_OBJECTS = re.compile(
    r"\b(?:image|images|photo|photos|pic|pics|picture|pictures|"
    r"tasveer|tasveeron|फोटो|तस्वीर|तस्वीरें|इमेज|पिक्चर)\b",
    re.IGNORECASE,
)

_MEDIA_ACTIONS = re.compile(
    r"\b(?:send|sent|show|find|search|fetch|get|retrieve|download|"
    r"open|share|bhej|bhejo|bhejna|dikha|dikhao|dikhana|dikhado|"
    r"nikal|nikalo|nikalna|lao|laana|dhoond|dhoondo|dhund|dhundho|"
    r"ढूंढो|दिखाओ|भेजो|निकालो)\b",
    re.IGNORECASE,
)

_MEDIA_REQUESTS = re.compile(
    r"\b(?:chahiye|chaahiye|do|de|dena|please|plz|want|need|"
    r"milega|milegi|mil|करो|चाहिए|दो|देना)\b",
    re.IGNORECASE,
)

_TOOL_INTENTS = re.compile(
    r"\b(?:r2|mcp|vectorize|github|docker|deploy|debug|process|"
    r"transcript|catalog|pending|enhance|api|code|error|exception|"
    r"workflow|database|repo|repository|object|key|file|video|audio|"
    r"voice\s+note|list|search)\b",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _is_media_request(text: str) -> bool:
    """Detect an actual media retrieval/request intent, not mere discussion."""
    if not _MEDIA_OBJECTS.search(text):
        return False

    # Object + action is the strong signal. Object + request language covers
    # natural phrases such as "black dress wali photo chahiye".
    return bool(_MEDIA_ACTIONS.search(text) or _MEDIA_REQUESTS.search(text))


def route_task(user_text: str) -> str:
    """Return 'tools' or 'chat'.

    The router chooses the model boundary only. Once routed to tools,
    Groq decides which MCP/tool operation is appropriate.
    """
    text = _normalize(user_text)
    if not text:
        return "chat"

    if _is_media_request(text):
        return "tools"

    if _TOOL_INTENTS.search(text):
        return "tools"

    return "chat"
