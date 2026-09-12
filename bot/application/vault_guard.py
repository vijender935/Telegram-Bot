"""Per-user vault authentication guard with rate limiting and temporary lockout."""
from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class VaultAttempt:
    failures: int = 0
    locked_until: float = 0.0


class VaultGuard:
    def __init__(self, max_attempts: int = 5, lockout_seconds: int = 900):
        self.max_attempts = max(1, max_attempts)
        self.lockout_seconds = max(1, lockout_seconds)
        self._state: dict[int, VaultAttempt] = {}

    def can_attempt(self, user_id: int) -> tuple[bool, int]:
        state = self._state.get(user_id, VaultAttempt())
        remaining = max(0, int(state.locked_until - time.monotonic()))
        return remaining == 0, remaining

    def success(self, user_id: int) -> None:
        self._state.pop(user_id, None)

    def failure(self, user_id: int) -> int:
        state = self._state.setdefault(user_id, VaultAttempt())
        state.failures += 1
        if state.failures >= self.max_attempts:
            state.failures = 0
            state.locked_until = time.monotonic() + self.lockout_seconds
        return max(0, int(state.locked_until - time.monotonic()))
