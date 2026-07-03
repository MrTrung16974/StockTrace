"""Vietnam stock exchange trading hours helpers."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

VN_TIMEZONE = ZoneInfo("Asia/Ho_Chi_Minh")

# HOSE / HNX — giờ giao dịch thường (ICT)
MORNING_SESSION_OPEN = time(9, 0)
MORNING_SESSION_CLOSE = time(11, 30)
AFTERNOON_SESSION_OPEN = time(13, 0)
AFTERNOON_SESSION_CLOSE = time(14, 45)


def is_vn_market_open(at: datetime, *, timezone: ZoneInfo = VN_TIMEZONE) -> bool:
    """Return whether Vietnam equities are in regular trading hours."""
    local = at.astimezone(timezone) if at.tzinfo is not None else at.replace(tzinfo=timezone)
    if local.weekday() >= 5:
        return False

    current = local.time()
    in_morning = MORNING_SESSION_OPEN <= current <= MORNING_SESSION_CLOSE
    in_afternoon = AFTERNOON_SESSION_OPEN <= current <= AFTERNOON_SESSION_CLOSE
    return in_morning or in_afternoon
