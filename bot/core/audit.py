"""Minimal security audit events. Never log secrets or media payloads."""
from __future__ import annotations

import logging

logger = logging.getLogger("security.audit")


def record(event: str, user_id: int, **metadata) -> None:
    safe = {k: v for k, v in metadata.items() if k not in {"code", "token", "password", "secret", "file_id"}}
    logger.info("audit event=%s user=%s meta=%s", event, user_id, safe)
