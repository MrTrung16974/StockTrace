"""ASCII chart visualization engine for financial dashboards."""

from __future__ import annotations

from decimal import Decimal

from stocktrace.domain.entities.financial import (
    ChartDataPoint,
    ChartMetadata,
    ChartSeries,
    CompanyFundamental,
    FinancialAnalysis,
    FinancialDashboard,
    FinancialScore,
    FinancialStatement,
    Valuation,
)

_RECOMMENDATION_VI = {
    "STRONG SELL": "BÁN MẠNH",
    "SELL": "BÁN",
    "HOLD": "NẮM GIỮ",
    "BUY": "MUA",
    "STRONG BUY": "MUA MẠNH",
}
_VALUATION_STATUS_VI = {
    "UNDERVALUED": "ĐANG RẺ",
    "FAIR": "HỢP LÝ",
    "OVERVALUED": "ĐANG ĐẮT",
}


def _translate_recommendation(value: str) -> str:
    return _RECOMMENDATION_VI.get(value, value)


def _translate_valuation_status(value: str) -> str:
    return _VALUATION_STATUS_VI.get(value, value)


def _format_billion(value: Decimal) -> str:
    """Format value in billions."""
    billions = value / Decimal("1000000000")
    if billions >= Decimal("1000"):
        return f"{billions / Decimal('1000'):.0f}k"
    return f"{billions:.0f}"


def _bar(value: Decimal, max_val: Decimal, width: int = 10) -> str:
    """Render a horizontal bar."""
    if max_val <= 0:
        return "░" * width
    filled = int((value / max_val) * width)
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def _ascii_line_chart(
    title: str,
    points: tuple[ChartDataPoint, ...],
    unit: str = "",
    height: int = 5,
) -> str:
    """Render a simple ASCII line chart."""
    if not points:
        return f"{title}\n(no data)"

    values = [float(p.value) for p in points]
    labels = [p.label for p in points]
    max_val = max(values) if values else 1
    min_val = min(values) if values else 0
    val_range = max_val - min_val or 1

    lines = [title]
    if unit:
        lines[0] += f" ({unit})"

    for row in range(height, 0, -1):
        threshold = min_val + (val_range * row / height)
        row_label = _format_billion(Decimal(str(threshold))) if unit else f"{threshold:.0f}"
        row_chars = []
        for v in values:
            if v >= threshold:
                row_chars.append("●")
            else:
                row_chars.append(" ")
        lines.append(f"{row_label:>4} |{' '.join(row_chars)}")

    lines.append("     " + "-" * (len(points) * 2 + 2))
    lines.append("      " + "  ".join(labels))
    return "\n".join(lines)


def _ascii_bar_chart(
    title: str,
    points: tuple[ChartDataPoint, ...],
    unit: str = "",
) -> str:
    """Render a vertical bar chart."""
    if not points:
        return f"{title}\n(no data)"

    values = [float(p.value) for p in points]
    labels = [p.label for p in points]
    max_val = max(values) if values else 1
    height = 5

    lines = [title]
    if unit:
        lines[0] += f" ({unit})"

    for row in range(height, 0, -1):
        threshold = max_val * row / height
        row_label = _format_billion(Decimal(str(threshold))) if unit else f"{threshold:.0f}"
        row_chars = []
        for v in values:
            row_chars.append("█" if v >= threshold else " ")
        lines.append(f"{row_label:>4} ┤{' '.join(row_chars)}")

    lines.append("     └" + "─" * (len(points) * 2 + 2))
    lines.append("      " + "  ".join(labels))
    return "\n".join(lines)


class FinancialVisualizationEngine:
    """Generate visual dashboard charts and formatted output."""

    def build_dashboard(self, analysis: FinancialAnalysis) -> FinancialDashboard:
        """Build complete visual dashboard from analysis."""
        charts = (
            self._revenue_profit_chart(analysis.statements),
            self._health_score_chart(analysis.score),
            self._revenue_structure_chart(analysis.fundamentals),
            self._valuation_chart(analysis.valuation),
            self._cashflow_chart(analysis.statements),
        )

        telegram_html = self._build_telegram_html(analysis, charts)
        json_payload = self._build_json_payload(analysis, charts)

        return FinancialDashboard(
            analysis=analysis,
            charts=charts,
            telegram_html=telegram_html,
            json_payload=json_payload,
        )

    def _revenue_profit_chart(
        self,
        statements: tuple[FinancialStatement, ...],
    ) -> ChartMetadata:
        revenue_points = tuple(ChartDataPoint(s.period, s.income.revenue) for s in statements)
        profit_points = tuple(ChartDataPoint(s.period, s.income.net_income) for s in statements)

        revenue_series = ChartSeries("Doanh thu", revenue_points, "Tỷ đồng")
        profit_series = ChartSeries("Lợi nhuận", profit_points, "Tỷ đồng")

        ascii_render = (
            _ascii_line_chart("Doanh thu", revenue_points, "Tỷ đồng")
            + "\n\n"
            + _ascii_line_chart("Lợi nhuận", profit_points, "Tỷ đồng")
        )

        return ChartMetadata(
            chart_id="revenue_profit_trend",
            chart_type="line",
            title="Xu hướng doanh thu và lợi nhuận",
            series=(revenue_series, profit_series),
            ascii_render=ascii_render,
        )

    def _health_score_chart(self, score: FinancialScore) -> ChartMetadata:
        categories = (
            ChartDataPoint("Tăng trưởng", score.growth_score * Decimal("10")),
            ChartDataPoint("Sinh lời", score.profitability_score * Decimal("10")),
            ChartDataPoint("Dòng tiền", score.cash_flow_score * Decimal("10")),
            ChartDataPoint("Nợ", score.debt_score * Decimal("10")),
            ChartDataPoint("Định giá", score.valuation_score * Decimal("10")),
        )

        lines = ["Điểm sức khỏe tài chính"]
        for cat in categories:
            bar = _bar(cat.value, Decimal("100"))
            lines.append(f"{cat.label:<14} {bar} {cat.value:.0f}")

        return ChartMetadata(
            chart_id="financial_health_score",
            chart_type="bar",
            title="Điểm sức khỏe tài chính",
            series=(ChartSeries("Điểm", categories, "%"),),
            ascii_render="\n".join(lines),
        )

    def _revenue_structure_chart(
        self,
        fundamentals: CompanyFundamental,
    ) -> ChartMetadata:
        segments = fundamentals.revenue_segments
        points = tuple(ChartDataPoint(s.name, s.percentage) for s in segments)

        lines = ["Cơ cấu doanh thu"]
        for seg in segments:
            lines.append(f"{seg.name:<15} {seg.percentage:.0f}%")

        if segments:
            lines.append("")
            lines.append(self._ascii_pie(segments))

        return ChartMetadata(
            chart_id="revenue_structure",
            chart_type="pie",
            title="Cơ cấu doanh thu",
            series=(ChartSeries("Phân khúc", points, "%"),),
            ascii_render="\n".join(lines),
        )

    def _ascii_pie(self, segments: tuple) -> str:
        """Simple ASCII pie representation."""
        if not segments:
            return ""
        largest = max(segments, key=lambda s: s.percentage)
        blocks = int(largest.percentage / 5)
        pie = "█" * blocks
        return f"    {pie}\n   {largest.name}"

    def _valuation_chart(self, valuation: Valuation) -> ChartMetadata:
        pe_points = tuple(ChartDataPoint(str(year), pe) for year, pe in valuation.historical_pe)

        ascii_render = _ascii_line_chart("PE lịch sử", pe_points, "PE")
        ascii_render += "\n\n"
        ascii_render += "\n".join(
            [
                (
                    f"PE hiện tại : {valuation.current_pe:.1f}"
                    if valuation.current_pe
                    else "PE hiện tại : Chưa có"
                ),
                (
                    f"PE trung bình : {valuation.average_pe:.1f}"
                    if valuation.average_pe
                    else "PE trung bình : Chưa có"
                ),
                f"Trạng thái : {_translate_valuation_status(valuation.status.value)}",
            ],
        )

        return ChartMetadata(
            chart_id="valuation",
            chart_type="line",
            title="Định giá",
            series=(ChartSeries("PE", pe_points, "PE"),),
            ascii_render=ascii_render,
        )

    def _cashflow_chart(
        self,
        statements: tuple[FinancialStatement, ...],
    ) -> ChartMetadata:
        cf_points = tuple(
            ChartDataPoint(s.period, s.cash_flow.operating_cash_flow) for s in statements
        )

        return ChartMetadata(
            chart_id="cashflow_trend",
            chart_type="bar",
            title="Dòng tiền từ hoạt động kinh doanh",
            series=(ChartSeries("Dòng tiền HĐKD", cf_points, "Tỷ đồng"),),
            ascii_render=_ascii_bar_chart("Dòng tiền HĐKD", cf_points, "Tỷ đồng"),
        )

    def _build_telegram_html(
        self,
        analysis: FinancialAnalysis,
        charts: tuple[ChartMetadata, ...],
    ) -> str:
        """Build HTML-formatted Telegram dashboard message."""
        score = analysis.score
        ai = analysis.ai_analysis

        period_str = (
            f"{analysis.period_start.strftime('%m/%Y')} → "
            f"{analysis.period_end.strftime('%m/%Y')}"
        )

        header = [
            f"<b>{analysis.company_name}</b>",
            "Báo cáo phân tích tài chính",
            f"Kỳ: {period_str}",
            f"Nguồn dữ liệu: {analysis.fundamentals.data_source}",
            f"Số kỳ báo cáo: {len(analysis.statements)}",
            f"Chất lượng dữ liệu: {analysis.quality.score:.0f}/100",
            "",
            f"Tín hiệu định lượng: <b>{_translate_recommendation(score.recommendation.value)}</b>",
            f"Độ tin cậy : {self._confidence(score)}%",
            f"Điểm tài chính: {score.overall_score} / 10",
        ]
        if analysis.fundamentals.is_mock_data:
            header.extend(
                [
                    "",
                    "⚠ <b>DỮ LIỆU MÔ PHỎNG</b>: chỉ dùng để kiểm thử, "
                    "không dùng cho quyết định đầu tư.",
                ],
            )
        else:
            header.append("Lưu ý: tín hiệu định lượng không phải khuyến nghị đầu tư.")
        if analysis.quality.issues:
            header.extend(
                [
                    "",
                    "<b>Điều kiện chưa đạt</b>",
                    *(f"• {issue}" for issue in analysis.quality.issues),
                ],
            )

        chart_blocks = []
        for chart in charts:
            chart_blocks.extend(
                ["", f"<b>{chart.title}</b>", "<pre>", chart.ascii_render, "</pre>"],
            )

        strengths = []
        risks = []
        if ai:
            strengths = [f"✓ {s}" for s in ai.strengths]
            risks = [f"⚠ {r}" for r in ai.risks]
        else:
            for sig in analysis.signals:
                if sig.level.value == "green":
                    strengths.extend(f"✓ {r}" for r in sig.reasons)
                elif sig.level.value == "red":
                    risks.extend(f"⚠ {r}" for r in sig.reasons)

        strength_block = ["", "<b>ĐIỂM MẠNH</b>"] + (
            strengths or ["✓ Chưa phát hiện điểm mạnh đáng kể"]
        )
        risk_block = ["", "<b>RỦI RO</b>"] + (risks or ["⚠ Chưa phát hiện rủi ro đáng kể"])

        ai_block: list[str] = []
        if ai:
            ai_block = [
                "",
                "<b>TÓM TẮT AI</b>",
                ai.executive_summary,
                "",
                f"Khuyến nghị: <b>{_translate_recommendation(ai.recommendation.value)}</b>",
            ]
            if ai.target_price:
                ai_block.append(f"Giá mục tiêu: {ai.target_price:,.0f} VND")
            ai_block.append(f"Độ tin cậy: {ai.confidence:.0f}%")

        signal_icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
        alert_block = ["", "<b>TÍN HIỆU CẢNH BÁO</b>"]
        for sig in analysis.signals:
            icon = signal_icons.get(sig.level.value, "⚪")
            alert_block.append(f"{icon} {sig.label}")

        parts = header + chart_blocks + strength_block + risk_block + ai_block + alert_block
        return "\n".join(parts)

    def _confidence(self, score: FinancialScore) -> int:
        """Derive confidence from score."""
        return min(99, max(50, int(float(score.overall_score) * 10)))

    def _build_json_payload(
        self,
        analysis: FinancialAnalysis,
        charts: tuple[ChartMetadata, ...],
    ) -> dict:
        """Build structured JSON response."""
        score = analysis.score
        return {
            "symbol": analysis.symbol,
            "company_name": analysis.company_name,
            "period": {
                "start": analysis.period_start.isoformat(),
                "end": analysis.period_end.isoformat(),
                "label": analysis.period_label,
            },
            "recommendation": score.recommendation.value,
            "confidence": self._confidence(score),
            "financial_score": float(score.overall_score),
            "scores": {
                "growth": float(score.growth_score),
                "profitability": float(score.profitability_score),
                "debt": float(score.debt_score),
                "cash_flow": float(score.cash_flow_score),
                "valuation": float(score.valuation_score),
            },
            "valuation": {
                "current_pe": (
                    float(analysis.valuation.current_pe) if analysis.valuation.current_pe else None
                ),
                "average_pe": (
                    float(analysis.valuation.average_pe) if analysis.valuation.average_pe else None
                ),
                "status": analysis.valuation.status.value,
                "target_price": (
                    float(analysis.valuation.target_price)
                    if analysis.valuation.target_price
                    else None
                ),
            },
            "charts": [
                {
                    "id": c.chart_id,
                    "type": c.chart_type,
                    "title": c.title,
                    "series": [
                        {
                            "name": s.name,
                            "unit": s.unit,
                            "points": [
                                {"label": p.label, "value": float(p.value)} for p in s.points
                            ],
                        }
                        for s in c.series
                    ],
                }
                for c in charts
            ],
            "signals": [
                {
                    "type": s.trace_type.value,
                    "level": s.level.value,
                    "label": s.label,
                    "reasons": list(s.reasons),
                }
                for s in analysis.signals
            ],
            "ai_summary": (
                {
                    "executive_summary": analysis.ai_analysis.executive_summary,
                    "strengths": list(analysis.ai_analysis.strengths),
                    "weaknesses": list(analysis.ai_analysis.weaknesses),
                    "risks": list(analysis.ai_analysis.risks),
                    "recommendation": analysis.ai_analysis.recommendation.value,
                    "confidence": float(analysis.ai_analysis.confidence),
                    "target_price": (
                        float(analysis.ai_analysis.target_price)
                        if analysis.ai_analysis.target_price
                        else None
                    ),
                }
                if analysis.ai_analysis
                else None
            ),
        }
