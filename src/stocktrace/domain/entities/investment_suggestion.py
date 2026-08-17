"""Safe, deterministic contracts for investment suggestions and draft trade intents.

These models deliberately contain no broker, LLM, HTTP, or Telegram dependency.
They define data that later phases may validate, explain, audit, and—only after
additional risk and confirmation gates—turn into a broker order.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

_SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}$")
_DISCLAIMER = (
    "Thông tin chỉ nhằm mục đích tham khảo, không phải khuyến nghị đầu tư "
    "hay cam kết lợi nhuận."
)


class SuggestionAction(StrEnum):
    """Actions produced by deterministic investment rules."""

    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    WATCH = "WATCH"
    ACCUMULATE_CONDITIONALLY = "ACCUMULATE_CONDITIONALLY"
    HOLD = "HOLD"
    REDUCE_CONDITIONALLY = "REDUCE_CONDITIONALLY"
    AVOID = "AVOID"


class InvestmentHorizon(StrEnum):
    """Time horizon supplied to the rule engine."""

    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


class SuggestionRiskLevel(StrEnum):
    """Risk classification shown alongside every suggestion."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceDirection(StrEnum):
    """Whether a verified factor supports or contradicts an action."""

    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"


class TradeSide(StrEnum):
    """A draft intent's permitted trade side."""

    BUY = "BUY"
    SELL = "SELL"


class DraftOrderType(StrEnum):
    """Only limit orders are allowed in the initial real-order boundary."""

    LIMIT = "LIMIT"


class QuantityPolicy(StrEnum):
    """Quantity policy permitted before a dedicated sizing engine exists."""

    FIXED_QUANTITY = "FIXED_QUANTITY"


class TradeIntentOrigin(StrEnum):
    """The only permitted source for a trade-intent draft."""

    RULE_ENGINE = "RULE_ENGINE"


class TradeIntentState(StrEnum):
    """Phase-2 state: the intent is not confirmed or submitted."""

    DRAFT = "DRAFT"


@dataclass(frozen=True, slots=True)
class SuggestionEvidence:
    """One verifiable factor used by a suggestion."""

    factor_code: str
    label: str
    value: str
    direction: EvidenceDirection
    source: str
    observed_at: datetime
    source_url: str | None = None

    def __post_init__(self) -> None:
        _require_text(self.factor_code, "factor_code")
        _require_text(self.label, "label")
        _require_text(self.value, "value")
        _require_text(self.source, "source")
        _require_aware_time(self.observed_at, "observed_at")


@dataclass(frozen=True, slots=True)
class DataFreshness:
    """Freshness contract for an input source consumed by a suggestion."""

    data_type: str
    source: str
    observed_at: datetime
    ttl: timedelta

    def __post_init__(self) -> None:
        _require_text(self.data_type, "data_type")
        _require_text(self.source, "source")
        _require_aware_time(self.observed_at, "observed_at")
        if self.ttl <= timedelta(0):
            raise ValueError("ttl must be greater than zero.")

    def is_fresh_at(self, checked_at: datetime) -> bool:
        """Return whether this source is fresh at the supplied aware timestamp."""
        _require_aware_time(checked_at, "checked_at")
        return checked_at <= self.observed_at + self.ttl


@dataclass(frozen=True, slots=True)
class InvalidationCondition:
    """A condition that makes the suggestion no longer actionable."""

    code: str
    description: str

    def __post_init__(self) -> None:
        _require_text(self.code, "code")
        _require_text(self.description, "description")


@dataclass(frozen=True, slots=True)
class InvestmentSuggestion:
    """A data-backed, auditable suggestion—not an order or trade authorization."""

    symbol: str
    action: SuggestionAction
    horizon: InvestmentHorizon
    risk_level: SuggestionRiskLevel
    confidence: Decimal
    evidence: tuple[SuggestionEvidence, ...]
    freshness: tuple[DataFreshness, ...]
    invalidation_conditions: tuple[InvalidationCondition, ...]
    rule_version: str
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    suggestion_id: str = field(default_factory=lambda: str(uuid4()))
    disclaimer: str = _DISCLAIMER

    def __post_init__(self) -> None:
        _require_symbol(self.symbol)
        _require_decimal_range(self.confidence, "confidence", Decimal("0"), Decimal("1"))
        if not self.evidence:
            raise ValueError("evidence must not be empty.")
        if not self.freshness:
            raise ValueError("freshness must not be empty.")
        if not self.invalidation_conditions:
            raise ValueError("invalidation_conditions must not be empty.")
        _require_text(self.rule_version, "rule_version")
        _require_text(self.suggestion_id, "suggestion_id")
        _require_text(self.disclaimer, "disclaimer")
        _require_aware_time(self.generated_at, "generated_at")


@dataclass(frozen=True, slots=True)
class TradeIntentDraft:
    """Deterministic draft only; confirmation and broker submission are future phases."""

    owner_id: str
    account_reference: str
    suggestion_id: str
    symbol: str
    suggestion_action: SuggestionAction
    side: TradeSide
    quantity: int
    limit_price: Decimal
    quantity_policy: QuantityPolicy = QuantityPolicy.FIXED_QUANTITY
    order_type: DraftOrderType = DraftOrderType.LIMIT
    origin: TradeIntentOrigin = TradeIntentOrigin.RULE_ENGINE
    state: TradeIntentState = TradeIntentState.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    intent_id: str = field(default_factory=lambda: str(uuid4()))

    def __post_init__(self) -> None:
        _require_text(self.owner_id, "owner_id")
        _require_text(self.account_reference, "account_reference")
        _require_text(self.suggestion_id, "suggestion_id")
        _require_symbol(self.symbol)
        _require_text(self.intent_id, "intent_id")
        _require_aware_time(self.created_at, "created_at")
        if self.quantity <= 0:
            raise ValueError("quantity must be greater than zero.")
        if self.limit_price <= 0:
            raise ValueError("limit_price must be greater than zero.")
        if self.quantity_policy is not QuantityPolicy.FIXED_QUANTITY:
            raise ValueError("Only FIXED_QUANTITY is supported for a draft trade intent.")
        if self.order_type is not DraftOrderType.LIMIT:
            raise ValueError("Only LIMIT orders are supported for a draft trade intent.")
        if self.origin is not TradeIntentOrigin.RULE_ENGINE:
            raise ValueError("Trade intents must originate from the deterministic rule engine.")
        if self.state is not TradeIntentState.DRAFT:
            raise ValueError("Phase-2 trade intents must remain in DRAFT state.")
        if self.suggestion_action is SuggestionAction.ACCUMULATE_CONDITIONALLY:
            if self.side is not TradeSide.BUY:
                raise ValueError("ACCUMULATE_CONDITIONALLY requires a BUY draft intent.")
            return
        if self.suggestion_action is SuggestionAction.REDUCE_CONDITIONALLY:
            if self.side is not TradeSide.SELL:
                raise ValueError("REDUCE_CONDITIONALLY requires a SELL draft intent.")
            return
        raise ValueError(
            "Only conditional accumulate or reduce suggestions can create a draft intent.",
        )


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_symbol(symbol: str) -> None:
    if not _SYMBOL_PATTERN.fullmatch(symbol):
        raise ValueError("symbol must be uppercase alphanumeric and 2-10 characters.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _require_decimal_range(value: Decimal, field_name: str, low: Decimal, high: Decimal) -> None:
    if not low <= value <= high:
        raise ValueError(f"{field_name} must be between {low} and {high}.")
