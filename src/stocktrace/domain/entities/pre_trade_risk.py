"""Immutable pre-trade risk policy and decision contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum


class RiskControlCode(StrEnum):
    """Deterministic controls that can block an order before submission."""

    ACCOUNT_UNAVAILABLE = "ACCOUNT_UNAVAILABLE"
    ACCOUNT_OWNER_MISMATCH = "ACCOUNT_OWNER_MISMATCH"
    MAX_QUANTITY_EXCEEDED = "MAX_QUANTITY_EXCEEDED"
    MAX_NOTIONAL_EXCEEDED = "MAX_NOTIONAL_EXCEEDED"
    DAILY_ORDER_LIMIT_EXCEEDED = "DAILY_ORDER_LIMIT_EXCEEDED"
    INSUFFICIENT_CASH = "INSUFFICIENT_CASH"
    INSUFFICIENT_POSITION = "INSUFFICIENT_POSITION"


@dataclass(frozen=True, slots=True)
class RiskPolicy:
    """Per-evaluation risk limits supplied by an approved policy configuration."""

    max_quantity_per_order: int
    max_notional_per_order: Decimal
    max_orders_per_day: int
    policy_version: str

    def __post_init__(self) -> None:
        if self.max_quantity_per_order <= 0:
            raise ValueError("max_quantity_per_order must be greater than zero.")
        if self.max_notional_per_order <= 0:
            raise ValueError("max_notional_per_order must be greater than zero.")
        if self.max_orders_per_day <= 0:
            raise ValueError("max_orders_per_day must be greater than zero.")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty.")


@dataclass(frozen=True, slots=True)
class RiskViolation:
    """One explicit risk-control failure, safe to retain in an audit snapshot."""

    code: RiskControlCode
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, RiskControlCode):
            raise ValueError("code must be a RiskControlCode.")
        if not self.message.strip():
            raise ValueError("message must not be empty.")


@dataclass(frozen=True, slots=True)
class PreTradeRiskDecision:
    """Result of risk checks for exactly one draft intent and account state."""

    intent_id: str
    account_reference: str
    is_approved: bool
    violations: tuple[RiskViolation, ...]
    policy_version: str
    checked_at: datetime

    def __post_init__(self) -> None:
        if not self.intent_id.strip():
            raise ValueError("intent_id must not be empty.")
        if not self.account_reference.strip():
            raise ValueError("account_reference must not be empty.")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty.")
        if any(not isinstance(item, RiskViolation) for item in self.violations):
            raise ValueError("violations must contain RiskViolation values.")
        if self.checked_at.tzinfo is None or self.checked_at.utcoffset() is None:
            raise ValueError("checked_at must be timezone-aware.")
        if self.is_approved and self.violations:
            raise ValueError("approved risk decision must not have violations.")
        if not self.is_approved and not self.violations:
            raise ValueError("rejected risk decision requires at least one violation.")
