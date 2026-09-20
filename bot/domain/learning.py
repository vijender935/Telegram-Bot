"""User preference learning — stable profile growth without model fine-tuning."""
from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_PROFILE: dict[str, Any] = {
    "name": None,
    "language": None,
    "reply_style": None,
    "likes": [],
    "dislikes": [],
    "notes": [],
}

REMEMBER_PATTERNS = (
    r"\byaad\s*rakh\b", r"\bremember\b", r"\bmujhe\s+pasand\b", r"\bi\s+like\b",
    r"\bi\s+love\b", r"\bmera\s+naam\b", r"\bcall\s+me\b",
    r"\bprefer\b", r"\bpasand\s+(?:nahi|nahin)\s+hai\b", r"\bpasand\s+hai\b",
    r"\b(?:mujhe|main)\s+(?:hamesha|usually|generally)\b",
    r"\b(?:mujhe|main)\s+(?:short|long|detailed|detail)\b",
    r"\b(?:don't|do not|never)\s+(?:like|want|prefer)\b",
    r"\b(?:samajh|samjh)\s+(?:aata|aati|aate)\s+(?:hai|hain)\b",
    r"\bmeri\s+preference\b",
    r"\breply\s+(?:short|long|medium|detail|detailed)\b",
    r"\bdetail\s+mein\s+(?:samjha|bata)\b",
    r"\bexamples?\s+(?:ke\s+saath|with)\b",
)


def empty_profile() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_PROFILE))


def profile_to_prompt_text(profile: dict | None) -> str:
    if not profile:
        return "(abhi koi stable user preference recorded nahi hai)"
    lines = []
    if profile.get("name"):
        lines.append(f"- Name / call: {profile['name']}")
    if profile.get("language"):
        lines.append(f"- Language: {profile['language']}")
    if profile.get("reply_style"):
        lines.append(f"- Reply style: {profile['reply_style']}")
    if profile.get("likes"):
        lines.append(f"- Likes: {', '.join(profile['likes'][:8])}")
    if profile.get("dislikes"):
        lines.append(f"- Dislikes: {', '.join(profile['dislikes'][:6])}")
    if profile.get("notes"):
        lines.append(f"- Notes: {'; '.join(profile['notes'][:6])}")
    return "\n".join(lines) if lines else "(profile almost empty)"


def should_extract(user_text: str) -> bool:
    low = (user_text or "").lower().strip()
    if not low:
        return False
    if any(re.search(pattern, low) for pattern in REMEMBER_PATTERNS):
        return True
    preference_words = (
        "pasand", "prefer", "yaad", "like", "love", "hate", "naam", "call me",
        "reply", "samjhao", "explain", "detail mein", "examples", "style", "tone",
        "language", "hinglish", "hindi", "english", "mat bolo", "mat karna",
    )
    return len(low) > 60 and any(word in low for word in preference_words)


def merge_profiles(old: dict, new: dict) -> dict:
    out = empty_profile()
    out.update({k: old.get(k) for k in DEFAULT_PROFILE if k in (old or {})})
    for key in ("name", "language", "reply_style"):
        val = new.get(key)
        if val:
            out[key] = val
    for key in ("likes", "dislikes", "notes"):
        seen = []
        for item in (out.get(key) or []) + (new.get(key) or []):
            s = str(item).strip()
            if s and s.lower() not in {x.lower() for x in seen}:
                seen.append(s)
        out[key] = seen[:12]
    return out


async def extract_and_merge(llm, existing: dict, user_message: str, bot_reply: str) -> dict:
    """One bounded LLM call to update stable user preferences; failure means no profile change."""
    from bot.agent.prompts import PROFILE_EXTRACT_PROMPT
    prompt = PROFILE_EXTRACT_PROMPT.format(
        existing_profile=json.dumps(existing or empty_profile(), ensure_ascii=False),
        user_message=user_message[:1500],
        bot_reply=(bot_reply or "")[:1500],
    )
    try:
        resp = await llm.ainvoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        text = text.strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        if not isinstance(data, dict):
            return existing or empty_profile()
        return merge_profiles(existing or empty_profile(), data)
    except Exception:
        logger.exception("profile extract failed")
        return existing or empty_profile()
