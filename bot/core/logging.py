"""Structured logging helpers."""
from __future__ import annotations

import logging


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
        force=True,
    )
    for name in ("httpx", "telegram", "googleapiclient"):
        logging.getLogger(name).setLevel(logging.WARNING)
