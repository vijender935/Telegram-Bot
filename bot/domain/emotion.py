"""Lightweight emotion / energy detection from user text (no extra LLM call)."""
from __future__ import annotations

import re

# label -> keywords
_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("horny", (
        "chod", "lund", "chut", "gaand", "sex", "horny", "geeli", "jhad", "cum",
        "fuck", "nude", "nangi", "panty", "boobs", "nipple", "suck", "blow",
        "dirty", "gandi", "garam", "mast", "hot", "ah", "mmm", "uff", "physical",
        "bed", "bistar", "raat", "night", "touch", "chu",
    )),
    ("dominant", (
        "dominate", "mistress", "slave", "kutta", "saza", "punish", "obey",
        "hukum", "control", "kaabu",
    )),
    ("soft", (
        "miss", "pyaar", "love", "hug", "romantic", "soft", "cuddle", "yaad",
        "dil", "sweet", "partner", "humsafar", "jaan", "baby", "shona",
    )),
    ("bored", (
        "boring", "bore", "kuch nahi", "idle", "timepass",
    )),
    ("eager", (
        "aur bhej", "more", "next", "another", "jaldi", "abhi", "please",
    )),
]


def detect_emotion(text: str) -> str:
    low = (text or "").lower()
    if not low.strip():
        return "neutral"
    scores: dict[str, int] = {}
    for label, kws in _RULES:
        scores[label] = sum(1 for k in kws if k in low)
    best = max(scores, key=scores.get)
    if scores[best] <= 0:
        # punctuation / length hints
        if "!" in text or re.search(r"\b(uff|ahh|mmm|oh+)\b", low):
            return "horny"
        return "neutral"
    return best
