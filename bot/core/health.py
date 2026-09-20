"""Health/readiness checks used by the HTTP endpoint and CI smoke tests."""
from __future__ import annotations

from pathlib import Path


def check_health(config, memory_path: str) -> dict:
    try:
        from bot.infra.transcribe import ffmpeg_available
        ffmpeg_ok = ffmpeg_available()
    except Exception:
        ffmpeg_ok = False
    checks = {
        "database_path": Path(memory_path).parent.exists(),
        "ffmpeg": ffmpeg_ok,
        "telegram_configured": bool(config.TELEGRAM_TOKEN),
        "ai_configured": bool(config.GROQ_API_KEY and config.GROQ_MODEL),
    }
    return {"status": "ok" if all(checks.values()) else "degraded", "checks": checks}
