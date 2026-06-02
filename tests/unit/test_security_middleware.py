"""Security middleware unit tests."""

from __future__ import annotations

from stocktrace.api.middleware.security import FixedWindowRateLimiter


def test_fixed_window_rate_limiter_blocks_after_limit() -> None:
    limiter = FixedWindowRateLimiter(limit=1)

    assert limiter.allow("client") is True
    assert limiter.allow("client") is False
