"""Price alert scheduled job."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stocktrace.infrastructure.scheduler.service import SchedulerService


class PriceAlertJob:
    """Delegate price alerts to the scheduler service."""

    def __init__(self, scheduler: SchedulerService) -> None:
        self._scheduler = scheduler

    async def run(self) -> None:
        """Execute price alert job."""
        await self._scheduler.send_price_alert()
