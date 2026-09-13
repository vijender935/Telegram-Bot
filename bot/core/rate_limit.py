"""Backward-compatible import for the rate limiter."""
from bot.core.security import SlidingWindowRateLimiter

__all__ = ["SlidingWindowRateLimiter"]
