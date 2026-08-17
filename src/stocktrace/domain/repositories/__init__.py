"""Domain repository contracts package for Phase 1."""

from stocktrace.domain.repositories.auto_trade_approval import AutoTradeApprovalRepository
from stocktrace.domain.repositories.auto_trade_control import AutoTradeControlRepository
from stocktrace.domain.repositories.paper_confirmation import PaperConfirmationRepository

__all__ = [
    "AutoTradeApprovalRepository",
    "AutoTradeControlRepository",
    "PaperConfirmationRepository",
]
