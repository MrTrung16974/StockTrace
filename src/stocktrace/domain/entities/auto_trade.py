"""Fail-closed pilot auto-trading approval and limit contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

_SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}$")


class AutoTradeApprovalStatus(StrEnum):
    """Lifecycle of an explicitly manual auto-trading pilot approval."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


@dataclass(frozen=True, slots=True)
class PaperTradingReadinessEvidence:
    """Immutable evidence that paper trading was observed before pilot automation."""

    evidence_id: str
    owner_id: str
    account_reference: str
    observation_started_at: datetime
    observation_ended_at: datetime
    completed_order_count: int
    is_stable: bool

    def __post_init__(self) -> None:
        _require_text(self.evidence_id, "evidence_id")
        _require_text(self.owner_id, "owner_id")
        _require_text(self.account_reference, "account_reference")
        _require_aware_time(self.observation_started_at, "observation_started_at")
        _require_aware_time(self.observation_ended_at, "observation_ended_at")
        if self.observation_ended_at < self.observation_started_at:
            raise ValueError("observation_ended_at must not precede observation_started_at.")
        if self.completed_order_count < 0:
            raise ValueError("completed_order_count must not be negative.")

    @property
    def observation_duration(self) -> timedelta:
        """Return the completed paper-trading observation window."""
        return self.observation_ended_at - self.observation_started_at


@dataclass(frozen=True, slots=True)
class AutoTradeApprovalRecord:
    """A manual authority record; a configuration switch can never replace it."""

    approval_id: str
    owner_id: str
    account_reference: str
    approved_by: str
    approved_at: datetime
    expires_at: datetime
    paper_trading_evidence: PaperTradingReadinessEvidence
    status: AutoTradeApprovalStatus = AutoTradeApprovalStatus.ACTIVE
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.approval_id, "approval_id"),
            (self.owner_id, "owner_id"),
            (self.account_reference, "account_reference"),
            (self.approved_by, "approved_by"),
        ):
            _require_text(value, field_name)
        _require_aware_time(self.approved_at, "approved_at")
        _require_aware_time(self.expires_at, "expires_at")
        if self.expires_at <= self.approved_at:
            raise ValueError("expires_at must be after approved_at.")
        if self.paper_trading_evidence.owner_id != self.owner_id:
            raise ValueError("paper-trading evidence must belong to the approval owner.")
        if self.paper_trading_evidence.account_reference != self.account_reference:
            raise ValueError("paper-trading evidence must belong to the approval account.")
        if self.approved_at < self.paper_trading_evidence.observation_ended_at:
            raise ValueError("manual approval must follow the paper-trading observation.")
        if self.status is AutoTradeApprovalStatus.ACTIVE and self.revoked_at is not None:
            raise ValueError("active approval must not have revoked_at.")
        if self.status is AutoTradeApprovalStatus.REVOKED:
            if self.revoked_at is None:
                raise ValueError("revoked approval requires revoked_at.")
            _require_aware_time(self.revoked_at, "revoked_at")
            if self.revoked_at < self.approved_at:
                raise ValueError("revoked_at must not precede approved_at.")

    def is_active_at(self, now: datetime) -> bool:
        """Return whether manually granted authority remains usable at ``now``."""
        _require_aware_time(now, "now")
        return self.status is AutoTradeApprovalStatus.ACTIVE and now < self.expires_at

    def revoke(self, *, revoked_at: datetime) -> AutoTradeApprovalRecord:
        """Return a terminal revoked approval record."""
        _require_aware_time(revoked_at, "revoked_at")
        if self.status is AutoTradeApprovalStatus.REVOKED:
            return self
        return replace(
            self,
            status=AutoTradeApprovalStatus.REVOKED,
            revoked_at=revoked_at,
        )


@dataclass(frozen=True, slots=True)
class AutoTradePilotPolicy:
    """Small, explicit pilot limits that are necessary but never sufficient alone."""

    enabled: bool
    allowed_symbols: tuple[str, ...]
    max_notional_per_order: Decimal
    max_notional_per_day: Decimal
    max_orders_per_day: int
    minimum_paper_observation: timedelta
    minimum_paper_completed_orders: int
    policy_version: str

    def __post_init__(self) -> None:
        if self.max_notional_per_order <= 0:
            raise ValueError("max_notional_per_order must be greater than zero.")
        if self.max_notional_per_day <= 0:
            raise ValueError("max_notional_per_day must be greater than zero.")
        if self.max_notional_per_order > self.max_notional_per_day:
            raise ValueError("per-order notional must not exceed the daily pilot limit.")
        if self.max_orders_per_day <= 0:
            raise ValueError("max_orders_per_day must be greater than zero.")
        if self.minimum_paper_observation <= timedelta(0):
            raise ValueError("minimum_paper_observation must be greater than zero.")
        if self.minimum_paper_completed_orders <= 0:
            raise ValueError("minimum_paper_completed_orders must be greater than zero.")
        if not self.policy_version.strip():
            raise ValueError("policy_version must not be empty.")
        if len(set(self.allowed_symbols)) != len(self.allowed_symbols):
            raise ValueError("allowed_symbols must not contain duplicates.")
        for symbol in self.allowed_symbols:
            if not _SYMBOL_PATTERN.fullmatch(symbol):
                raise ValueError("allowed_symbols must contain uppercase symbols.")
        if self.enabled and not self.allowed_symbols:
            raise ValueError("an enabled auto-trade pilot requires allowed_symbols.")


class AutoTradeBlockCode(StrEnum):
    """Explicit fail-closed reasons returned by the pilot gate."""

    AUTOMATION_DISABLED = "AUTOMATION_DISABLED"
    PRE_TRADE_RISK_NOT_APPROVED = "PRE_TRADE_RISK_NOT_APPROVED"
    APPROVAL_MISSING = "APPROVAL_MISSING"
    APPROVAL_OWNER_MISMATCH = "APPROVAL_OWNER_MISMATCH"
    APPROVAL_ACCOUNT_MISMATCH = "APPROVAL_ACCOUNT_MISMATCH"
    APPROVAL_REVOKED = "APPROVAL_REVOKED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    PAPER_TRADING_UNSTABLE = "PAPER_TRADING_UNSTABLE"
    PAPER_TRADING_OBSERVATION_TOO_SHORT = "PAPER_TRADING_OBSERVATION_TOO_SHORT"
    PAPER_TRADING_ORDER_COUNT_TOO_LOW = "PAPER_TRADING_ORDER_COUNT_TOO_LOW"
    SYMBOL_NOT_ALLOWED = "SYMBOL_NOT_ALLOWED"
    MAX_ORDER_NOTIONAL_EXCEEDED = "MAX_ORDER_NOTIONAL_EXCEEDED"
    DAILY_ORDER_LIMIT_EXCEEDED = "DAILY_ORDER_LIMIT_EXCEEDED"
    DAILY_NOTIONAL_LIMIT_EXCEEDED = "DAILY_NOTIONAL_LIMIT_EXCEEDED"
    CONTROL_STATE_UNAVAILABLE = "CONTROL_STATE_UNAVAILABLE"
    KILL_SWITCH_ACTIVE = "KILL_SWITCH_ACTIVE"
    OWNER_NOT_IN_ROLLOUT = "OWNER_NOT_IN_ROLLOUT"


@dataclass(frozen=True, slots=True)
class AutoTradeGateDecision:
    """Auditable result of evaluating one intent against the pilot's hard gates."""

    decision_id: str
    intent_id: str
    account_reference: str
    approval_id: str | None
    policy_version: str
    is_authorized: bool
    blocks: tuple[AutoTradeBlockCode, ...]
    checked_at: datetime
    checksum: str

    def __post_init__(self) -> None:
        _require_text(self.decision_id, "decision_id")
        _require_text(self.intent_id, "intent_id")
        _require_text(self.account_reference, "account_reference")
        _require_text(self.policy_version, "policy_version")
        _require_aware_time(self.checked_at, "checked_at")
        if not re.fullmatch(r"[a-f0-9]{64}", self.checksum):
            raise ValueError("checksum must be a lowercase SHA-256 hex digest.")
        if self.is_authorized and self.blocks:
            raise ValueError("authorized decision must not carry blocks.")
        if not self.is_authorized and not self.blocks:
            raise ValueError("blocked decision requires at least one block code.")

    @classmethod
    def create(
        cls,
        *,
        decision_id: str,
        intent_id: str,
        account_reference: str,
        approval_id: str | None,
        policy_version: str,
        is_authorized: bool,
        blocks: tuple[AutoTradeBlockCode, ...],
        checked_at: datetime,
    ) -> AutoTradeGateDecision:
        """Create a tamper-evident snapshot of one pilot-gate evaluation."""
        snapshot = cls(
            decision_id=decision_id,
            intent_id=intent_id,
            account_reference=account_reference,
            approval_id=approval_id,
            policy_version=policy_version,
            is_authorized=is_authorized,
            blocks=blocks,
            checked_at=checked_at,
            checksum="0" * 64,
        )
        return cls(
            decision_id=snapshot.decision_id,
            intent_id=snapshot.intent_id,
            account_reference=snapshot.account_reference,
            approval_id=snapshot.approval_id,
            policy_version=snapshot.policy_version,
            is_authorized=snapshot.is_authorized,
            blocks=snapshot.blocks,
            checked_at=snapshot.checked_at,
            checksum=_checksum_for(snapshot),
        )

    def has_valid_checksum(self) -> bool:
        """Return whether the decision's audit fields still match its checksum."""
        return self.checksum == _checksum_for(self)


def new_auto_trade_approval_id() -> str:
    """Generate an opaque manual-approval identifier."""
    return str(uuid4())


def new_auto_trade_decision_id() -> str:
    """Generate an opaque gate-decision identifier for audit correlation."""
    return str(uuid4())


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")


def _checksum_for(decision: AutoTradeGateDecision) -> str:
    payload = {
        "account_reference": decision.account_reference,
        "approval_id": decision.approval_id,
        "blocks": [block.value for block in decision.blocks],
        "checked_at": decision.checked_at.isoformat(),
        "decision_id": decision.decision_id,
        "intent_id": decision.intent_id,
        "is_authorized": decision.is_authorized,
        "policy_version": decision.policy_version,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
