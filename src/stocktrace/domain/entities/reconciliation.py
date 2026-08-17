"""Immutable reconciliation contracts for broker fills and tracked portfolios."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4


class ReconciliationStatus(StrEnum):
    """Whether a lifecycle has a safe portfolio update plan or needs review."""

    MATCHED = "MATCHED"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class ReconciliationIssueCode(StrEnum):
    """Explicit reasons why an automatic portfolio mutation is unsafe."""

    PORTFOLIO_OWNER_MISMATCH = "PORTFOLIO_OWNER_MISMATCH"
    BROKER_ACCOUNT_MISMATCH = "BROKER_ACCOUNT_MISMATCH"
    BROKER_OWNER_MISMATCH = "BROKER_OWNER_MISMATCH"
    SELL_QUANTITY_EXCEEDS_PORTFOLIO = "SELL_QUANTITY_EXCEEDS_PORTFOLIO"
    BROKER_POSITION_MISMATCH = "BROKER_POSITION_MISMATCH"


class PortfolioMutationKind(StrEnum):
    """The only portfolio changes a matched reconciliation may request."""

    UPSERT = "UPSERT"
    REMOVE = "REMOVE"


@dataclass(frozen=True, slots=True)
class PortfolioPositionSnapshot:
    """The internal portfolio baseline captured before applying one order's fills."""

    owner_id: str
    symbol: str
    quantity: int
    average_price: Decimal | None
    captured_at: datetime

    def __post_init__(self) -> None:
        _require_text(self.owner_id, "owner_id")
        _require_symbol(self.symbol)
        _require_aware_time(self.captured_at, "captured_at")
        if self.quantity < 0:
            raise ValueError("quantity must not be negative.")
        if self.quantity == 0 and self.average_price is not None:
            raise ValueError("empty position must not have average_price.")
        if self.quantity > 0 and (self.average_price is None or self.average_price <= 0):
            raise ValueError("held position requires a positive average_price.")


@dataclass(frozen=True, slots=True)
class PortfolioMutationPlan:
    """A single computed mutation that a durable transaction may apply once."""

    kind: PortfolioMutationKind
    owner_id: str
    symbol: str
    quantity: int
    average_price: Decimal | None

    def __post_init__(self) -> None:
        _require_text(self.owner_id, "owner_id")
        _require_symbol(self.symbol)
        if self.kind is PortfolioMutationKind.UPSERT:
            if self.quantity <= 0 or self.average_price is None or self.average_price <= 0:
                raise ValueError("upsert plan requires positive quantity and average_price.")
            return
        if self.kind is PortfolioMutationKind.REMOVE:
            if self.quantity != 0 or self.average_price is not None:
                raise ValueError("remove plan requires zero quantity and no average_price.")
            return
        raise ValueError("kind must be a PortfolioMutationKind.")


@dataclass(frozen=True, slots=True)
class ReconciliationResult:
    """Checksum-protected comparison of order fills against broker portfolio state."""

    reconciliation_id: str
    order_id: str
    lifecycle_checksum: str
    account_reference: str
    owner_id: str
    symbol: str
    status: ReconciliationStatus
    issues: tuple[ReconciliationIssueCode, ...]
    mutation_plan: PortfolioMutationPlan | None
    checked_at: datetime
    checksum: str

    def __post_init__(self) -> None:
        for value, field_name in (
            (self.reconciliation_id, "reconciliation_id"),
            (self.order_id, "order_id"),
            (self.lifecycle_checksum, "lifecycle_checksum"),
            (self.account_reference, "account_reference"),
            (self.owner_id, "owner_id"),
        ):
            _require_text(value, field_name)
        _require_symbol(self.symbol)
        _require_aware_time(self.checked_at, "checked_at")
        if not _CHECKSUM_PATTERN.fullmatch(self.lifecycle_checksum):
            raise ValueError("lifecycle_checksum must be a lowercase SHA-256 hex digest.")
        if not _CHECKSUM_PATTERN.fullmatch(self.checksum):
            raise ValueError("checksum must be a lowercase SHA-256 hex digest.")
        if self.status is ReconciliationStatus.MATCHED:
            if self.issues:
                raise ValueError("matched reconciliation must not have issues.")
            return
        if self.status is ReconciliationStatus.REQUIRES_REVIEW:
            if not self.issues or self.mutation_plan is not None:
                raise ValueError("review reconciliation needs issues and no mutation plan.")
            return
        raise ValueError("status must be a ReconciliationStatus.")

    @classmethod
    def create(
        cls,
        *,
        order_id: str,
        lifecycle_checksum: str,
        account_reference: str,
        owner_id: str,
        symbol: str,
        issues: tuple[ReconciliationIssueCode, ...],
        mutation_plan: PortfolioMutationPlan | None,
        checked_at: datetime,
        reconciliation_id: str | None = None,
    ) -> ReconciliationResult:
        """Create a tamper-evident result, fail-closing when any issue is present."""
        snapshot = cls(
            reconciliation_id=reconciliation_id or str(uuid4()),
            order_id=order_id,
            lifecycle_checksum=lifecycle_checksum,
            account_reference=account_reference,
            owner_id=owner_id,
            symbol=symbol,
            status=(
                ReconciliationStatus.REQUIRES_REVIEW
                if issues
                else ReconciliationStatus.MATCHED
            ),
            issues=issues,
            mutation_plan=None if issues else mutation_plan,
            checked_at=checked_at,
            checksum="0" * 64,
        )
        return cls(
            reconciliation_id=snapshot.reconciliation_id,
            order_id=snapshot.order_id,
            lifecycle_checksum=snapshot.lifecycle_checksum,
            account_reference=snapshot.account_reference,
            owner_id=snapshot.owner_id,
            symbol=snapshot.symbol,
            status=snapshot.status,
            issues=snapshot.issues,
            mutation_plan=snapshot.mutation_plan,
            checked_at=snapshot.checked_at,
            checksum=_checksum_for(snapshot),
        )

    @property
    def can_apply_portfolio_mutation(self) -> bool:
        """Return whether the plan is safe to apply once in a durable transaction."""
        return self.status is ReconciliationStatus.MATCHED and self.mutation_plan is not None

    def has_valid_checksum(self) -> bool:
        """Return whether audit fields still match their checksum."""
        return self.checksum == _checksum_for(self)


_CHECKSUM_PATTERN = re.compile(r"^[a-f0-9]{64}$")
_SYMBOL_PATTERN = re.compile(r"^[A-Z]{2,10}$")


def _checksum_for(result: ReconciliationResult) -> str:
    plan = result.mutation_plan
    payload = {
        "account_reference": result.account_reference,
        "checked_at": result.checked_at.isoformat(),
        "issues": [issue.value for issue in result.issues],
        "lifecycle_checksum": result.lifecycle_checksum,
        "mutation_plan": (
            None
            if plan is None
            else {
                "average_price": None if plan.average_price is None else str(plan.average_price),
                "kind": plan.kind.value,
                "owner_id": plan.owner_id,
                "quantity": plan.quantity,
                "symbol": plan.symbol,
            }
        ),
        "order_id": result.order_id,
        "owner_id": result.owner_id,
        "reconciliation_id": result.reconciliation_id,
        "status": result.status.value,
        "symbol": result.symbol,
    }
    canonical = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_symbol(value: str) -> None:
    if not _SYMBOL_PATTERN.fullmatch(value):
        raise ValueError("symbol must be uppercase alphanumeric and 2-10 characters.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
