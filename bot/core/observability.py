"""Small dependency-free observability primitives."""
from __future__ import annotations

import logging
import time
import uuid
from collections import Counter
from contextlib import contextmanager

class Metrics:
    def __init__(self):
        self._counts = Counter()
        self._latency_ms: list[float] = []

    def inc(self, name: str, value: int = 1) -> None:
        self._counts[name] += value

    @contextmanager
    def timer(self, name: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            self._latency_ms.append((time.perf_counter() - started) * 1000)
            self.inc(name)
            if len(self._latency_ms) > 1000:
                del self._latency_ms[:-1000]

    def snapshot(self) -> dict:
        latency = sorted(self._latency_ms)
        p95 = latency[min(len(latency) - 1, int(len(latency) * 0.95))] if latency else 0.0
        return {"counters": dict(self._counts), "latency_ms_p95": round(p95, 2)}

metrics = Metrics()
logger = logging.getLogger(__name__)

def request_id() -> str:
    return uuid.uuid4().hex[:16]

def log_event(event: str, **fields) -> None:
    safe = " ".join(f"{k}={v!s}" for k, v in fields.items() if v is not None)
    logger.info("event=%s %s", event, safe)
