"""Vietnam market hours tests."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from stocktrace.infrastructure.scheduler.market_hours import VN_TIMEZONE, is_vn_market_open

VN = VN_TIMEZONE


def test_market_open_during_morning_session() -> None:
    at = datetime(2026, 6, 8, 10, 0, tzinfo=VN)  # Monday
    assert is_vn_market_open(at, timezone=VN) is True


def test_market_open_during_afternoon_session() -> None:
    at = datetime(2026, 6, 8, 13, 30, tzinfo=VN)  # Monday
    assert is_vn_market_open(at, timezone=VN) is True


def test_market_closed_during_lunch_break() -> None:
    at = datetime(2026, 6, 8, 12, 0, tzinfo=VN)  # Monday
    assert is_vn_market_open(at, timezone=VN) is False


def test_market_closed_on_weekend() -> None:
    at = datetime(2026, 6, 7, 10, 0, tzinfo=VN)  # Sunday
    assert is_vn_market_open(at, timezone=VN) is False


def test_market_closed_before_open() -> None:
    at = datetime(2026, 6, 8, 8, 30, tzinfo=VN)  # Monday
    assert is_vn_market_open(at, timezone=VN) is False


def test_market_closed_after_close() -> None:
    at = datetime(2026, 6, 8, 15, 0, tzinfo=VN)  # Monday
    assert is_vn_market_open(at, timezone=VN) is False
