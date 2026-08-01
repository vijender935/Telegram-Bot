"""User preference learning — profile grows from chat (not model fine-tune)."""
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
    "kinks": [],
    "soft_limits": [],
    "likes": [],
    "dislikes": [],
    "ongoing_fantasy": None,
    "notes": [],
}

REMEMBER_PATTERNS = (
    r"\byaad\s*rakh\b",
    r"\bremember\b",
    r"\bmujhe\s+pasand\b",
    r"\bi\s+like\b",
    r"\bi\s+love\b",
    r"\bmeri\s+fantasy\b",
    r"\bmera\s+naam\b",
    r"\bcall\s+me\b",
)


def empty_profile() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_PROFILE))


def profile_to_prompt_text(profile: dict | None) -> str:
    if not profile:
        return "(abhi kuch special yaad nahi — naye partner ki tarah jaan rahi hoon)"
    lines = []
    if profile.get("name"):
        lines.append(f"- Name / call: {profile['name']}")
    if profile.get("language"):
        lines.append(f"- Language: {profile['language']}")
    if profile.get("reply_style"):
        lines.append(f"- Reply style: {profile['reply_style']}")
    if profile.get("kinks"):
        lines.append(f"- Kinks: {', '.join(profile['kinks'][:8])}")
    if profile.get("soft_limits"):
        lines.append(f"- Soft limits: {', '.join(profile['soft_limits'][:6])}")
    if profile.get("likes"):
        lines.append(f"- Likes: {', '.join(profile['likes'][:8])}")
    if profile.get("dislikes"):
        lines.append(f"- Dislikes: {', '.join(profile['dislikes'][:6])}")
    if profile.get("ongoing_fantasy"):
        lines.append(f"- Ongoing fantasy: {profile['ongoing_fantasy']}")
    if profile.get("notes"):
        lines.append(f"- Notes: {'; '.join(profile['notes'][:6])}")
    return "\n".join(lines) if lines else "(profile almost empty)"


def should_extract(user_text: str) -> bool:
    low = (user_text or "").lower()
    if any(re.search(p, low) for p in REMEMBER_PATTERNS):
        return True
    # longer personal messages worth mining occasionally
    return len(low) > 80 and any(
        w in low for w in ("pasand", "fantasy", "yaad", "like", "hate", "naam", "call me")
    )


def merge_profiles(old: dict, new: dict) -> dict:
    out = empty_profile()
    out.update({k: old.get(k) for k in DEFAULT_PROFILE if k in (old or {})})

    for key in ("name", "language", "reply_style", "ongoing_fantasy"):
        val = new.get(key)
        if val:
            out[key] = val

    for key in ("kinks", "soft_limits", "likes", "dislikes", "notes"):
        seen = []
        for item in (out.get(key) or []) + (new.get(key) or []):
            s = str(item).strip()
            if s and s.lower() not in {x.lower() for x in seen}:
                seen.append(s)
        out[key] = seen[:12]
    return out


async def extract_and_merge(llm, existing: dict, user_message: str, bot_reply: str) -> dict:
    """One cheap LLM call to update profile. Failures = no change."""
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
