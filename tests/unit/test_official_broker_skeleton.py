"""Tests that an unapproved real-broker adapter fails closed."""

from __future__ import annotations

import pytest

from stocktrace.domain.ports.broker_execution import BrokerIntegrationNotConfiguredError
from stocktrace.infrastructure.brokers.official_broker_skeleton import OfficialBrokerSkeleton


@pytest.mark.asyncio
async def test_official_broker_skeleton_never_claims_account_access() -> None:
    broker = OfficialBrokerSkeleton("candidate-broker")

    with pytest.raises(BrokerIntegrationNotConfiguredError, match="Phase 1"):
        await broker.get_account("account-1")


def test_official_broker_skeleton_requires_a_candidate_name() -> None:
    with pytest.raises(ValueError, match="broker_name"):
        OfficialBrokerSkeleton(" ")
