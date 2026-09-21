"""Telegram presentation copy."""
from __future__ import annotations

def home_text(name: str | None = None) -> str:
    greeting = f"Hey {name} 👋" if name else "Hey 👋"
    return (
        f"{greeting}\n\n"
        "Main tumhara AI companion hoon — chat, memory, files, images aur supported tools ke saath.\n\n"
        "Bas normal language mein bolo. /help se commands dekh sakte ho."
    )

def help_text() -> str:
    return (
        "🧭 Commands\n\n"
        "/start — onboarding\n"
        "/help — capabilities\n"
        "/profile — saved preferences\n"
        "/memory — current conversation memory\n"
        "/reset — history/profile reset\n"
        "/voice — latest reply ko voice note mein convert\n\n"
        "Baaki kaam normal language mein bolo."
    )

def profile_text(profile: dict | None) -> str:
    if not profile:
        return "👤 Profile\n\nAbhi koi stable preference saved nahi hai."
    lines = ["👤 Profile", ""]
    for key, label in (("name", "Name"), ("language", "Language"), ("reply_style", "Reply style")):
        if profile.get(key):
            lines.append(f"{label}: {profile[key]}")
    for key, label in (("likes", "Likes"), ("dislikes", "Dislikes"), ("notes", "Notes")):
        values = profile.get(key) or []
        if values:
            lines.append(f"{label}: " + ", ".join(str(v) for v in values[:8]))
    return "\n".join(lines)

def memory_text(summary: str, count: int) -> str:
    return (
        "🧠 Memory\n\n"
        f"Messages in current session: {count}\n\n"
        f"{summary or 'Abhi koi session summary nahi hai.'}"
    )
