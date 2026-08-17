"""Scheduled expiry of paper-confirmation requests, with no Telegram delivery."""

from __future__ import annotations

from stocktrace.application.services.paper_confirmation import PaperConfirmationService
from stocktrace.infrastructure.logging.config import get_logger


class PaperConfirmationExpiryJob:
    """Expire stale confirmation requests before a paper broker can receive them."""

    def __init__(self, service: PaperConfirmationService) -> None:
        self._service = service
        self._logger = get_logger(__name__)

    async def run(self) -> None:
        """Expire due records and retain only a non-sensitive operational count."""
        expired_count = await self._service.expire_due()
        self._logger.info("paper_confirmation_expiry_completed", expired_count=expired_count)
