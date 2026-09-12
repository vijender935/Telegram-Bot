"""Deterministic response policy used to steer style, depth and follow-up behaviour."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResponsePolicy:
    mode: str
    language: str
    length: str
    should_ask: bool
    should_explain: bool

    def to_prompt(self) -> str:
        return (
            f"mode={self.mode}; language={self.language}; length={self.length}; "
            f"ask_followup={self.should_ask}; explain={self.should_explain}"
        )


def infer_response_policy(user_text: str, profile: dict | None = None) -> ResponsePolicy:
    text = (user_text or "").strip().lower()
    profile = profile or {}
    preferred_language = profile.get("language") or "hinglish"
    preferred_length = profile.get("reply_style") or "adaptive"

    explicit_short = any(x in text for x in ("short reply", "short mein", "chhota answer", "brief batao"))
    explicit_detail = any(x in text for x in ("detail mein", "detailed", "step by step", "examples ke saath", "deep dive"))
    technical = any(
        token in text
        for token in (
            "code", "python", "github", "api", "mcp", "rag", "database", "workflow",
            "error", "exception", "architecture", "deploy", "docker", "programming",
            "implementation", "implement", "debug", "bug", "explain", "kaise",
        )
    )
    question = text.endswith("?") or any(
        text.startswith(prefix)
        for prefix in ("what ", "why ", "how ", "where ", "when ", "what's ", "kya ", "kyun ", "kaise ", "kab ", "kahan ")
    )
    casual = any(text.startswith(g) for g in ("hi", "hii", "hello", "hey", "haan", "ok", "accha", "lol", "haha"))

    if explicit_short:
        return ResponsePolicy("concise", preferred_language, "short", False, False)
    if technical or explicit_detail:
        return ResponsePolicy("technical", preferred_language, "detailed", question, True)
    if casual and len(text.split()) <= 6:
        return ResponsePolicy("casual", preferred_language, "short", False, False)
    if question:
        return ResponsePolicy("answer", preferred_language, "adaptive", False, False)
    if preferred_length in {"short", "medium", "long"}:
        return ResponsePolicy("conversation", preferred_language, preferred_length, False, False)
    return ResponsePolicy("conversation", preferred_language, "adaptive", False, False)
