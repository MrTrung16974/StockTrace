"""Tests for scheduled Telegram delivery of suggestion-change alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest

from stocktrace.application.services.suggestion_alerts import SuggestionAlertService
from stocktrace.domain.entities.investment_suggestion import (
    DataFreshness,
    EvidenceDirection,
    InvalidationCondition,
    InvestmentHorizon,
    InvestmentSuggestion,
    SuggestionAction,
    SuggestionEvidence,
    SuggestionRiskLevel,
)
from stocktrace.infrastructure.config import SchedulerSettings, Settings, TelegramSettings
from stocktrace.infrastructure.scheduler.suggestion_alert_job import SuggestionAlertJob

NOW = datetime.now(tz=UTC)


class FakeBot:
    """Telegram test double that records notification-only sends."""

    def __init__(self) -> None:
        self.messages: list[dict[str, Any]] = []

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        disable_web_page_preview: bool | None = None,
    ) -> None:
        self.messages.append({"chat_id": chat_id, "text": text, "parse_mode": parse_mode})


class SequenceCollector:
    """Return one verified suggestion batch per scheduler run."""

    def __init__(self, batches: list[tuple[InvestmentSuggestion, ...]]) -> None:
        self._batches = iter(batches)

    async def __call__(self) -> tuple[InvestmentSuggestion, ...]:
        return next(self._batches)


def _suggestion(action: SuggestionAction) -> InvestmentSuggestion:
    return InvestmentSuggestion(
        symbol="HPG",
        action=action,
        horizon=InvestmentHorizon.MEDIUM,
        risk_level=SuggestionRiskLevel.MEDIUM,
        confidence=Decimal("0.60"),
        evidence=(
            SuggestionEvidence(
                "FINANCIAL_SCORE",
                "Điểm tài chính",
                "0.60",
                EvidenceDirection.SUPPORTS,
                "vnstock",
                NOW,
            ),
        ),
        freshness=(DataFreshness("quote", "exchange-feed", NOW, timedelta(hours=1)),),
        invalidation_conditions=(InvalidationCondition("STALE", "Dữ liệu đã cũ."),),
        rule_version="suggestion-rules-v1",
        generated_at=NOW,
    )


@pytest.mark.asyncio
async def test_job_sends_notification_only_after_a_suggestion_change() -> None:
    bot = FakeBot()
    job = SuggestionAlertJob(
        collector=SequenceCollector(
            [
                (_suggestion(SuggestionAction.WATCH),),
                (_suggestion(SuggestionAction.ACCUMULATE_CONDITIONALLY),),
            ],
        ),
        alert_service=SuggestionAlertService(),
        bot=bot,
        settings=Settings(
            _env_file=None,
            telegram=TelegramSettings(chat_id="chat-1"),
            scheduler=SchedulerSettings(suggestion_alert_enabled=True),
        ),
    )

    await job.run()
    await job.run()

    assert len(bot.messages) == 1
    assert "GỢI Ý ĐÃ THAY ĐỔI" in bot.messages[0]["text"]
    assert "xác nhận" in bot.messages[0]["text"]
    assert "http" not in bot.messages[0]["text"]
