"""Paper-only trading adapters; no real broker integration lives here."""

from stocktrace.infrastructure.paper_trading.in_memory_auto_trade_approval_repository import (
    InMemoryAutoTradeApprovalRepository,
)
from stocktrace.infrastructure.paper_trading.in_memory_auto_trade_control_repository import (
    InMemoryAutoTradeControlRepository,
)
from stocktrace.infrastructure.paper_trading.in_memory_confirmation_repository import (
    InMemoryPaperConfirmationRepository,
)
from stocktrace.infrastructure.paper_trading.paper_broker import PaperBroker

__all__ = [
    "InMemoryAutoTradeApprovalRepository",
    "InMemoryAutoTradeControlRepository",
    "InMemoryPaperConfirmationRepository",
    "PaperBroker",
]
