"""Small dependency-free observability primitives."""
from __future__ import annotations

import logging
import threading
import time
import uuid
from collections import Counter
from contextlib import contextmanager


class Metrics:
    def __init__(self):
        self._counts = Counter()
        self._latency_ms: list[float] = []
        self._lock = threading.Lock()

    def inc(self, name: str, value: int = 1) -> None:
        with self._lock:
            self._counts[name] += value

    @contextmanager
    def timer(self, name: str):
        started = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            with self._lock:
                self._latency_ms.append(elapsed_ms)
                if len(self._latency_ms) > 1000:
                    del self._latency_ms[:-1000]
                self._counts[name] += 1

    def snapshot(self) -> dict:
        with self._lock:
            latency = sorted(self._latency_ms)
            counts = dict(self._counts)
        p95 = latency[min(len(latency) - 1, int(len(latency) * 0.95))] if latency else 0.0
        return {"counters": counts, "latency_ms_p95": round(p95, 2)}

metrics = Metrics()
logger = logging.getLogger(__name__)


def request_id() -> str:
    return uuid.uuid4().hex[:16]


def log_event(event: str, **fields) -> None:
    safe = " ".join(f"{k}={v!s}" for k, v in fields.items() if v is not None)
    logger.info("event=%s %s", event, safe)
