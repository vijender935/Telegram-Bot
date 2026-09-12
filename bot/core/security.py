"""Small, dependency-free security primitives used by the bot."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """In-process limiter. Suitable for a single Telegram worker."""

    def __init__(self, limit: int = 8, window_seconds: int = 60):
        self.limit = max(1, limit)
        self.window = max(1, window_seconds)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        while hits and now - hits[0] >= self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


def hash_secret(secret: str, salt: bytes | None = None, rounds: int = 210_000) -> str:
    """PBKDF2-SHA256 hash; format is v2$rounds$salt$digest."""
    if not secret:
        raise ValueError("Secret cannot be empty")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), salt, rounds)
    return f"v2${rounds}${salt.hex()}${digest.hex()}"


def verify_secret(secret: str, encoded: str) -> bool:
    try:
        if not encoded.startswith("v2$"):
            return False
        _, rounds, salt_hex, digest_hex = encoded.split("$", 3)
        digest = hashlib.pbkdf2_hmac("sha256", secret.encode(), bytes.fromhex(salt_hex), int(rounds))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (TypeError, ValueError):
        return False
