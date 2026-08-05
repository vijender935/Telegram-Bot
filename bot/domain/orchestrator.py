"""Build rich context for chat + post-reply memory side effects."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bot import config
from bot.domain.emotion import detect_emotion
from bot.domain.media_context import (
    format_last_media,
    format_session_summary,
    format_active_fantasy,
)

logger = logging.getLogger(__name__)


def build_context_packet(memory, user_id: int, user_text: str = "") -> dict[str, Any]:
    emotion = detect_emotion(user_text) if user_text else memory.get_emotion(user_id)
    if user_text:
        memory.set_emotion(user_id, emotion)

    last_media = memory.get_last_media(user_id)
    session_summary, msg_count = memory.get_session(user_id)
    fantasy = memory.get_fantasy(user_id)
    profile = memory.get_profile(user_id)
    mood = memory.get_mood(user_id)

    # If user reacts to media, store short reaction
    if last_media and user_text and emotion in ("horny", "eager", "dominant"):
        memory.set_last_media_reaction(user_id, user_text[:120])

    # Time context generation
    now = datetime.now()
    hour = now.hour
    if 5 <= hour < 12:
        time_ctx = "Subah ka waqt hai, thoda sleepy aur fresh vibe."
    elif 12 <= hour < 17:
        time_ctx = "Dopehar ho rahi hai, busy din lekin tera khayal aa gaya."
    elif 17 <= hour < 21:
        time_ctx = "Shaam ka suhana waqt, relax karne ka mann hai."
    else:
        time_ctx = "Late night... sab shaant hai, bas main aur meri baatein."

    return {
        "mood": mood,
        "profile": profile,
        "emotion": emotion,
        "session_summary": session_summary,
        "msg_count": msg_count,
        "last_media": last_media,
        "last_media_text": format_last_media(last_media),
        "session_summary_text": format_session_summary(session_summary),
        "fantasy_text": format_active_fantasy(fantasy),
        "time_context": time_ctx,
    }


async def maybe_update_session_summary(llm, memory, user_id: int, user_text: str, bot_reply: str):
    """Every N messages, compress recent chat into a short session summary."""
    count = memory.bump_session_count(user_id)
    every = max(4, config.SESSION_SUMMARY_EVERY)
    if count % every != 0:
        return
    prev, _ = memory.get_session(user_id)
    prompt = (
        "Summarize this private chat session in 3-5 short Hinglish lines. "
        "Keep: ongoing fantasy, media shared, user preferences, mood. "
        "No markdown.\n\n"
        f"Previous summary:\n{prev or '(none)'}\n\n"
        f"User: {user_text[:800]}\n"
        f"Bot: {(bot_reply or '')[:800]}\n"
    )
    try:
        resp = await llm.ainvoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        text = (text or "").strip()[:800]
        if text:
            memory.set_session(user_id, text, count)
            logger.info("session summary updated user=%s count=%s", user_id, count)
    except Exception:
        logger.exception("session summary failed")


def media_followup_lines(description: str, mood: str) -> str:
    """Short lines after sending media — as if she sent it."""
    desc = (description or "").strip()
    snippet = desc[:180] + ("…" if len(desc) > 180 else "")
    mood_l = (mood or "").lower()
    if "soft" in mood_l or "romantic" in mood_l:
        return (
            f"yeh dekh…\n{snippet}\n\n"
            "bata kaisa laga. aaj thoda slow chal sakte hain."
        )
    if "rough" in mood_l or "punish" in mood_l or "femdom" in mood_l:
        return (
            f"yeh dekh ke bol.\n{snippet}\n\n"
            "ab ispe focus kar. distract mat ho."
        )
    return (
        f"yeh wali bheji maine…\n{snippet}\n\n"
        "bata — ispe kya karna hai next?"
    )
