"""Second-factor verification boundary for secure order confirmation."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class SecondFactorVerifier(Protocol):
    """Verify a one-time factor without exposing its enrollment secret to callers."""

    async def verify(self, owner_id: str, code: str, *, verified_at: datetime) -> bool:
        """Return true only for a valid, unused owner-bound factor code."""
