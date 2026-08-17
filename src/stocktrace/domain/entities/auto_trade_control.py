"""Operational kill-switch and deterministic rollout state for auto-trading."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import uuid4

MAX_ROLLOUT_PERCENTAGE = 100


@dataclass(frozen=True, slots=True)
class AutoTradeControlState:
    """Runtime control state, fail-closed until an authorized release exists.

    A rollout percentage is deterministic per owner, while explicitly listed pilot
    owners can be enabled independently. The kill switch overrides every policy.
    """

    state_id: str
    kill_switch_active: bool
    rollout_percentage: int
    rollout_owner_ids: tuple[str, ...]
    updated_by: str
    updated_at: datetime
    kill_switch_reason: str | None = None

    def __post_init__(self) -> None:
        for value, field_name in ((self.state_id, "state_id"), (self.updated_by, "updated_by")):
            _require_text(value, field_name)
        if not 0 <= self.rollout_percentage <= MAX_ROLLOUT_PERCENTAGE:
            raise ValueError("rollout_percentage must be between 0 and 100.")
        if len(set(self.rollout_owner_ids)) != len(self.rollout_owner_ids):
            raise ValueError("rollout_owner_ids must not contain duplicates.")
        for owner_id in self.rollout_owner_ids:
            _require_text(owner_id, "rollout_owner_ids item")
        _require_aware_time(self.updated_at, "updated_at")
        if self.kill_switch_active and not (self.kill_switch_reason or "").strip():
            raise ValueError("active kill switch requires a reason.")
        if not self.kill_switch_active and self.kill_switch_reason is not None:
            raise ValueError("inactive kill switch must not have a reason.")

    @classmethod
    def initially_killed(cls, *, updated_by: str, updated_at: datetime) -> AutoTradeControlState:
        """Create the deployment-safe default: all automation is stopped."""
        return cls(
            state_id=str(uuid4()),
            kill_switch_active=True,
            rollout_percentage=0,
            rollout_owner_ids=(),
            updated_by=updated_by,
            updated_at=updated_at,
            kill_switch_reason="Auto-trading is disabled until a separate release is approved.",
        )

    def activate_kill_switch(
        self,
        *,
        reason: str,
        updated_by: str,
        updated_at: datetime,
    ) -> AutoTradeControlState:
        """Return a terminal stop state which overrides all pilot approvals."""
        _require_text(reason, "reason")
        _require_text(updated_by, "updated_by")
        _require_aware_time(updated_at, "updated_at")
        if updated_at < self.updated_at:
            raise ValueError("updated_at must not precede prior control state.")
        return replace(
            self,
            kill_switch_active=True,
            updated_by=updated_by,
            updated_at=updated_at,
            kill_switch_reason=reason,
        )

    def is_owner_in_rollout(self, owner_id: str) -> bool:
        """Return deterministic rollout eligibility; kill status is checked separately."""
        _require_text(owner_id, "owner_id")
        if owner_id in self.rollout_owner_ids:
            return True
        bucket = int.from_bytes(hashlib.sha256(owner_id.encode("utf-8")).digest()[:4], "big") % 100
        return bucket < self.rollout_percentage


def _require_text(value: str, field_name: str) -> None:
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty.")


def _require_aware_time(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware.")
