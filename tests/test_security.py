import time

from bot.core.security import SlidingWindowRateLimiter, hash_secret, verify_secret
from bot.application.vault_guard import VaultGuard


def test_secret_hash_roundtrip():
    encoded = hash_secret("correct horse")
    assert encoded.startswith("v2$")
    assert verify_secret("correct horse", encoded)
    assert not verify_secret("wrong", encoded)


def test_rate_limiter():
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("u")
    assert limiter.allow("u")
    assert not limiter.allow("u")


def test_vault_lockout():
    guard = VaultGuard(max_attempts=2, lockout_seconds=60)
    assert guard.can_attempt(1)[0]
    assert guard.failure(1) == 0
    assert guard.failure(1) > 0
    assert not guard.can_attempt(1)[0]
    guard.success(1)
    assert guard.can_attempt(1)[0]
