"""Periodic, notification-only monitoring of verified investment suggestions."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from html import escape

from stocktrace.application.services.suggestion_alerts import (
    SuggestionAlert,
    SuggestionAlertKind,
    SuggestionAlertService,
)
from stocktrace.domain.entities.investment_suggestion import InvestmentSuggestion
from stocktrace.infrastructure.config.settings import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.scheduler.protocols import TelegramMessageBot

SuggestionCollector = Callable[[], Awaitable[tuple[InvestmentSuggestion, ...]]]


class SuggestionAlertJob:
    """Fetch verified suggestions and send notification-only Telegram alerts."""

    def __init__(
        self,
        collector: SuggestionCollector,
        alert_service: SuggestionAlertService,
        bot: TelegramMessageBot,
        settings: Settings,
    ) -> None:
        self._collector = collector
        self._alert_service = alert_service
        self._bot = bot
        self._settings = settings
        self._logger = get_logger(__name__)

    async def run(self) -> None:
        """Check for changes; an upstream failure produces no invented alert."""
        if not self._settings.scheduler.suggestion_alert_enabled:
            return
        chat_id = self._settings.telegram.chat_id
        if not chat_id:
            self._logger.info("suggestion_alert_job_skipped", reason="no_chat_id")
            return
        try:
            suggestions = await self._collector()
        except Exception as exc:
            self._logger.warning("suggestion_alert_collection_failed", error=str(exc))
            return

        alerts = self._alert_service.detect(suggestions, checked_at=datetime.now(UTC))
        for alert in alerts:
            try:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=_format_alert(alert),
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            except Exception as exc:
                self._logger.warning(
                    "suggestion_alert_delivery_failed",
                    symbol=alert.symbol,
                    kind=alert.kind.value,
                    error=str(exc),
                )


def _format_alert(alert: SuggestionAlert) -> str:
    """Render an informational alert without buttons, links, or trade actions."""
    symbol = escape(alert.symbol)
    if alert.kind is SuggestionAlertKind.INVALIDATED:
        return "\n".join(
            [
                "<b>⚠️ GỢI Ý KHÔNG CÒN HỢP LỆ</b>",
                f"Mã: <b>{symbol}</b>",
                "Dữ liệu dùng cho gợi ý đã hết hạn; không tạo hoặc xác nhận lệnh nào.",
            ],
        )
    if alert.kind is SuggestionAlertKind.ACTION_CHANGED:
        previous_action = escape(alert.previous.action.value) if alert.previous else "N/A"
        return "\n".join(
            [
                "<b>GỢI Ý ĐÃ THAY ĐỔI</b>",
                f"Mã: <b>{symbol}</b>",
                f"Action: {previous_action} → {escape(alert.current.action.value)}",
                "Thông báo chỉ để theo dõi; không phải xác nhận hay lệnh giao dịch.",
            ],
        )
    previous_risk = escape(alert.previous.risk_level.value) if alert.previous else "N/A"
    return "\n".join(
        [
            "<b>⚠️ MỨC RỦI RO ĐÃ THAY ĐỔI</b>",
            f"Mã: <b>{symbol}</b>",
            f"Rủi ro: {previous_risk} → {escape(alert.current.risk_level.value)}",
            "Thông báo chỉ để theo dõi; không phải xác nhận hay lệnh giao dịch.",
        ],
    )
