"""Deterministic response policy used to steer conversational style."""
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

    technical = any(
        token in text
        for token in (
            "code", "python", "github", "api", "mcp", "rag", "database", "workflow",
            "error", "exception", "architecture", "deploy", "docker", "explain", "kaise",
        )
    )
    question = text.endswith("?") or any(
        text.startswith(prefix) for prefix in ("what ", "why ", "how ", "kya ", "kyun ", "kaise ", "kab ")
    )
    casual = any(text.startswith(g) for g in ("hi", "hii", "hello", "hey", "haan", "ok", "accha"))

    if technical:
        return ResponsePolicy("technical", preferred_language, "detailed", question, True)
    if casual and len(text.split()) <= 5:
        return ResponsePolicy("casual", preferred_language, "short", False, False)
    if question:
        return ResponsePolicy("answer", preferred_language, "adaptive", True, False)
    if preferred_length in {"short", "medium", "long"}:
        return ResponsePolicy("conversation", preferred_language, preferred_length, False, False)
    return ResponsePolicy("conversation", preferred_language, "adaptive", False, False)
