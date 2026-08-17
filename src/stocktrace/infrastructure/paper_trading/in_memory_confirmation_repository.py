"""Transient repository for paper-confirmation workflow tests and local development."""

from __future__ import annotations

import asyncio
from datetime import datetime

from stocktrace.domain.entities.paper_confirmation import PaperTradeConfirmation


class InMemoryPaperConfirmationRepository:
    """Lock-protected in-memory store; never suitable for real order authorization."""

    def __init__(self) -> None:
        self._confirmations: dict[str, PaperTradeConfirmation] = {}
        self._lock = asyncio.Lock()

    async def save(self, confirmation: PaperTradeConfirmation) -> None:
        """Atomically store the latest immutable lifecycle snapshot."""
        async with self._lock:
            self._confirmations[confirmation.confirmation_id] = confirmation

    async def get(self, confirmation_id: str) -> PaperTradeConfirmation | None:
        """Return a confirmation snapshot by opaque identifier."""
        async with self._lock:
            return self._confirmations.get(confirmation_id)

    async def list_expired_pending(self, *, now: datetime) -> tuple[PaperTradeConfirmation, ...]:
        """List only pending confirmations that have reached their hard expiry."""
        async with self._lock:
            return tuple(
                confirmation
                for confirmation in self._confirmations.values()
                if confirmation.is_expired_at(now)
            )
