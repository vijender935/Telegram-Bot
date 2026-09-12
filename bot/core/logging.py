"""Structured logging helpers with secret redaction."""
from __future__ import annotations

import logging
import re

_SECRET_RE = re.compile(r"(?i)(token|api[_-]?key|password|secret|authorization)\s*[=:]\s*([^\s,]+)")


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )
    for name in ("httpx", "telegram", "googleapiclient"):
        logging.getLogger(name).setLevel(logging.WARNING)


def redact(value: object) -> str:
    return _SECRET_RE.sub(r"\1=[REDACTED]", str(value))
