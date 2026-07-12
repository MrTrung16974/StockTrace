"""Validation gates for financial statement analysis."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from stocktrace.domain.entities.financial import FinancialDataQuality, FinancialStatement

_MIN_TTM_QUARTERS = 4
_MIN_ANNUAL_PERIODS = 2
_BALANCE_TOLERANCE = Decimal("0.005")
_MAX_REPORT_AGE_DAYS = 190


class FinancialDataQualityEngine:
    """Reject or qualify analysis when source statements are insufficient."""

    def assess(
        self,
        statements: list[FinancialStatement],
        *,
        is_mock_data: bool,
        today: date | None = None,
    ) -> FinancialDataQuality:
        issues: list[str] = []
        if is_mock_data:
            issues.append("Nguồn dữ liệu mô phỏng không được dùng cho tín hiệu đầu tư.")

        periods_are_quarterly = all(
            statement.period.upper().startswith("Q") for statement in statements
        )
        if periods_are_quarterly and len(statements) < _MIN_TTM_QUARTERS:
            issues.append("Chưa đủ 4 quý liên tiếp để tính chỉ số TTM.")
        if not periods_are_quarterly and len(statements) < _MIN_ANNUAL_PERIODS:
            issues.append("Chưa đủ 2 năm tài chính để đánh giá xu hướng.")

        reference_date = today or date.today()
        if statements and (reference_date - statements[-1].period_end).days > _MAX_REPORT_AGE_DAYS:
            issues.append("Báo cáo tài chính mới nhất đã quá cũ.")

        for statement in statements:
            assets = statement.balance.total_assets
            accounting_gap = abs(
                assets - statement.balance.total_liabilities - statement.balance.total_equity,
            )
            if assets > 0 and accounting_gap / assets > _BALANCE_TOLERANCE:
                issues.append(
                    f"Bảng cân đối kỳ {statement.period} không cân: "
                    "Tài sản khác Nợ phải trả cộng Vốn chủ sở hữu.",
                )

        critical = bool(issues)
        score = Decimal("100") - Decimal("25") * Decimal(len(issues))
        score = max(Decimal("0"), score)
        return FinancialDataQuality(
            score=score,
            is_ready_for_analysis=bool(statements) and not is_mock_data,
            is_ready_for_investment_signal=not critical,
            issues=tuple(issues),
        )
