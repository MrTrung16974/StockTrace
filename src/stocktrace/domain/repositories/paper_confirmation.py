"""Persistence boundary for paper-confirmation lifecycle state."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from stocktrace.domain.entities.paper_confirmation import PaperTradeConfirmation


class PaperConfirmationRepository(Protocol):
    """Store confirmation records independently of Telegram and broker adapters."""

    async def save(self, confirmation: PaperTradeConfirmation) -> None:
        """Create or replace one confirmation by opaque identifier."""

    async def get(self, confirmation_id: str) -> PaperTradeConfirmation | None:
        """Return a confirmation by identifier."""

    async def list_expired_pending(self, *, now: datetime) -> tuple[PaperTradeConfirmation, ...]:
        """Return pending confirmations whose expiry has elapsed."""
