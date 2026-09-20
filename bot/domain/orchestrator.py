"""Build relevance-ranked context for the conversation engine."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bot import config
from bot.domain.media_context import format_last_media, format_session_summary

logger = logging.getLogger(__name__)


def _format_relevant_memories(memory, user_id: int, query: str, limit: int = 5) -> str:
    search = getattr(memory, "search_user", None)
    if not search or not query:
        return "(no relevant long-term memories)"
    try:
        results = search(user_id, query, limit=limit)
    except Exception:
        logger.exception("memory retrieval failed user=%s", user_id)
        return "(memory retrieval unavailable)"
    useful = [item for item in results if len(item) >= 3 and item[2] > 0.15]
    if not useful:
        return "(no relevant long-term memories)"
    return "\n".join(f"- {text[:500]} (relevance={score:.0%})" for _, text, score in useful)


def build_context_packet(memory, user_id: int, user_text: str = "") -> dict[str, Any]:
    last_media = memory.get_last_media(user_id)
    session_summary, msg_count = memory.get_session(user_id)
    profile = memory.get_profile(user_id)

    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        time_ctx = "morning"
    elif 12 <= hour < 17:
        time_ctx = "afternoon"
    elif 17 <= hour < 21:
        time_ctx = "evening"
    else:
        time_ctx = "late night"

    return {
        "profile": profile,
        "session_summary": session_summary,
        "msg_count": msg_count,
        "last_media": last_media,
        "last_media_text": format_last_media(last_media),
        "session_summary_text": format_session_summary(session_summary),
        "memory_context_text": _format_relevant_memories(memory, user_id, user_text),
        "time_context": time_ctx,
    }


async def maybe_update_session_summary(llm, memory, user_id: int, user_text: str, bot_reply: str):
    """Periodically compress the current conversation state without blocking chat."""
    count = memory.bump_session_count(user_id)
    every = max(4, config.SESSION_SUMMARY_EVERY)
    if count % every != 0:
        return
    prev, _ = memory.get_session(user_id)
    prompt = (
        "Summarize the current conversation state in 3-5 concise Hinglish lines. "
        "Keep only active topic, unresolved goal, useful preferences and important context. "
        "Do not invent facts and do not turn casual chatter into permanent preferences.\n\n"
        f"Previous summary:\n{prev or '(none)'}\n\n"
        f"User:\n{user_text[:800]}\n"
        f"Bot:\n{(bot_reply or '')[:800]}\n"
    )
    try:
        resp = await llm.ainvoke(prompt)
        text = (getattr(resp, "content", None) or str(resp) or "").strip()[:800]
        if text:
            memory.set_session(user_id, text, count)
            logger.info("session summary updated user=%s count=%s", user_id, count)
    except Exception:
        logger.exception("session summary failed")


def media_followup_lines(description: str) -> str:
    """Short follow-up after media delivery."""
    desc = (description or "").strip()
    snippet = desc[:180] + ("…" if len(desc) > 180 else "")
    return f"yeh dekho…\n{snippet}\n\nbatao, kaisa laga?"
