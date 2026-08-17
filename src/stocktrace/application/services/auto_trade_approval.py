"""Trusted manual approval workflow for a constrained auto-trading pilot."""

from __future__ import annotations

from datetime import UTC, datetime

from stocktrace.domain.entities.auto_trade import (
    AutoTradeApprovalRecord,
    AutoTradeApprovalStatus,
    PaperTradingReadinessEvidence,
    new_auto_trade_approval_id,
)
from stocktrace.domain.repositories.auto_trade_approval import AutoTradeApprovalRepository


class AutoTradeApprovalError(RuntimeError):
    """Base error for manual pilot approval operations."""


class AutoTradeApprovalAlreadyActiveError(AutoTradeApprovalError):
    """Raised when a pilot account already has active manual authority."""


class AutoTradeApprovalNotFoundError(AutoTradeApprovalError):
    """Raised when a requested manual approval record is unknown."""


class AutoTradeApprovalService:
    """Create and revoke approval records; callers must be a trusted admin boundary.

    This service does not authenticate an approver itself. A future secure admin UI
    must pass the authenticated authority identity; Telegram must never call it.
    """

    def __init__(self, repository: AutoTradeApprovalRepository) -> None:
        self._repository = repository

    async def approve(
        self,
        *,
        owner_id: str,
        account_reference: str,
        authorized_approver_id: str,
        paper_trading_evidence: PaperTradingReadinessEvidence,
        expires_at: datetime,
        approved_at: datetime | None = None,
    ) -> AutoTradeApprovalRecord:
        """Persist an explicit manual approval after a trusted authority action."""
        _require_text(owner_id, "owner_id")
        _require_text(account_reference, "account_reference")
        _require_text(authorized_approver_id, "authorized_approver_id")
        _require_aware_time(expires_at, "expires_at")
        timestamp = approved_at or datetime.now(UTC)
        _require_aware_time(timestamp, "approved_at")
        if paper_trading_evidence.owner_id != owner_id:
            raise ValueError("paper-trading evidence must belong to owner_id.")
        if paper_trading_evidence.account_reference != account_reference:
            raise ValueError("paper-trading evidence must belong to account_reference.")
        active = await self._repository.get_active(
            owner_id=owner_id,
            account_reference=account_reference,
        )
        if active is not None and active.is_active_at(timestamp):
            raise AutoTradeApprovalAlreadyActiveError("a manual pilot approval is already active.")
        approval = AutoTradeApprovalRecord(
            approval_id=new_auto_trade_approval_id(),
            owner_id=owner_id,
            account_reference=account_reference,
            approved_by=authorized_approver_id,
            approved_at=timestamp,
            expires_at=expires_at,
            paper_trading_evidence=paper_trading_evidence,
        )
        await self._repository.save(approval)
        return approval

    async def revoke(
        self,
        approval_id: str,
        *,
        revoked_at: datetime | None = None,
    ) -> AutoTradeApprovalRecord:
        """Revoke pilot authority immediately; no configuration change is required."""
        _require_text(approval_id, "approval_id")
        approval = await self._repository.get(approval_id)
        if approval is None:
            raise AutoTradeApprovalNotFoundError("manual pilot approval was not found.")
        if approval.status is AutoTradeApprovalStatus.REVOKED:
            return approval
        timestamp = revoked_at or datetime.now(UTC)
        _require_aware_time(timestamp, "revoked_at")
        revoked = approval.revoke(revoked_at=timestamp)
        await self._repository.save(revoked)
        return revoked


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
