"""AI-powered financial analysis service."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from stocktrace.ai.financial_models import FinancialAnalysisContext, FinancialAnalysisLLMResult
from stocktrace.ai.financial_prompt_builder import FinancialPromptBuilder
from stocktrace.domain.entities.financial import (
    AIFinancialAnalysis,
    FinancialAnalysis,
    Recommendation,
)
from stocktrace.domain.ports.llm_provider import LLMProvider
from stocktrace.infrastructure.config.settings import AISettings


def _parse_recommendation(text: str) -> Recommendation:
    """Parse recommendation from LLM text."""
    upper = text.upper().strip()
    for rec in Recommendation:
        if rec.value in upper:
            return rec
    if "BUY" in upper:
        return Recommendation.BUY
    if "SELL" in upper:
        return Recommendation.SELL
    return Recommendation.HOLD


def _parse_section(text: str, header: str) -> str:
    """Extract a section from structured LLM output."""
    pattern = rf"{header}:\s*\n(.*?)(?=\n[A-Z_]+:|$)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _parse_bullets(text: str) -> tuple[str, ...]:
    """Parse bullet points from section text."""
    lines = []
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("- "):
            lines.append(line[2:].strip())
        elif line.startswith("• "):
            lines.append(line[2:].strip())
    return tuple(lines)


def _parse_confidence(text: str) -> Decimal:
    """Parse confidence percentage."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        try:
            return Decimal(match.group(1))
        except InvalidOperation:
            pass
    return Decimal("75")


def _parse_target_price(text: str) -> Decimal | None:
    """Parse target price from text."""
    if "N/A" in text.upper():
        return None
    match = re.search(r"([\d,]+)", text.replace(",", ""))
    if match:
        try:
            return Decimal(match.group(1))
        except InvalidOperation:
            pass
    return None


class AIFinancialAnalysisService:
    """Generate LLM-powered financial analysis."""

    def __init__(
        self,
        llm: LLMProvider | None = None,
        prompt_builder: FinancialPromptBuilder | None = None,
        settings: AISettings | None = None,
    ) -> None:
        self._llm = llm
        self._prompt_builder = prompt_builder or FinancialPromptBuilder()
        self._settings = settings

    @property
    def is_enabled(self) -> bool:
        """Return whether AI analysis is available."""
        return self._llm is not None and (self._settings is None or self._settings.enabled)

    def build_context(self, analysis: FinancialAnalysis) -> FinancialAnalysisContext:
        """Build LLM context from financial analysis."""
        latest_ratio = analysis.ratios[-1] if analysis.ratios else None
        ratios_summary: dict[str, str] = {}
        if latest_ratio:
            if latest_ratio.roe is not None:
                ratios_summary["ROE"] = f"{latest_ratio.roe:.1f}%"
            if latest_ratio.revenue_growth is not None:
                ratios_summary["Revenue Growth"] = f"{latest_ratio.revenue_growth:.1f}%"
            if latest_ratio.net_margin is not None:
                ratios_summary["Net Margin"] = f"{latest_ratio.net_margin:.1f}%"
            if latest_ratio.debt_to_equity is not None:
                ratios_summary["Debt/Equity"] = f"{latest_ratio.debt_to_equity:.2f}"

        val = analysis.valuation
        valuation_summary = {
            "Current PE": f"{val.current_pe:.1f}" if val.current_pe else "N/A",
            "Average PE": f"{val.average_pe:.1f}" if val.average_pe else "N/A",
            "Status": val.status.value,
        }

        strengths = tuple(
            r for sig in analysis.signals if sig.level.value == "green" for r in sig.reasons
        )
        risks = tuple(
            r for sig in analysis.signals if sig.level.value == "red" for r in sig.reasons
        )

        return FinancialAnalysisContext(
            symbol=analysis.symbol,
            company_name=analysis.company_name,
            period_label=analysis.period_label,
            score=analysis.score,
            ratios_summary=ratios_summary,
            valuation_summary=valuation_summary,
            strengths_hints=strengths,
            risks_hints=risks,
        )

    async def analyze(self, financial_analysis: FinancialAnalysis) -> AIFinancialAnalysis | None:
        """Generate AI analysis for financial data."""
        if not self.is_enabled or self._llm is None:
            return self._fallback_analysis(financial_analysis)

        context = self.build_context(financial_analysis)
        prompt = self._prompt_builder.build(context)

        from stocktrace.ai.models import LLMRequest

        request = LLMRequest(
            prompt=prompt,
            system_prompt=FinancialPromptBuilder.SYSTEM_PROMPT,
            max_tokens=self._settings.max_tokens if self._settings else 1500,
            temperature=self._settings.temperature if self._settings else 0.3,
        )

        response = await self._llm.complete(request)
        parsed = self._parse_response(response.content)

        return AIFinancialAnalysis(
            symbol=financial_analysis.symbol,
            executive_summary=parsed.executive_summary,
            strengths=parsed.strengths,
            weaknesses=parsed.weaknesses,
            opportunities=parsed.opportunities,
            risks=parsed.risks,
            recommendation=parsed.recommendation,
            confidence=parsed.confidence,
            target_price=parsed.target_price or financial_analysis.valuation.target_price,
            raw_response=response.content,
        )

    def _parse_response(self, content: str) -> FinancialAnalysisLLMResult:
        """Parse structured LLM response."""
        exec_summary = _parse_section(content, "EXECUTIVE_SUMMARY")
        strengths = _parse_bullets(_parse_section(content, "STRENGTHS"))
        weaknesses = _parse_bullets(_parse_section(content, "WEAKNESSES"))
        opportunities = _parse_bullets(_parse_section(content, "OPPORTUNITIES"))
        risks = _parse_bullets(_parse_section(content, "RISKS"))
        rec_text = _parse_section(content, "RECOMMENDATION")
        conf_text = _parse_section(content, "CONFIDENCE")
        target_text = _parse_section(content, "TARGET_PRICE")

        return FinancialAnalysisLLMResult(
            executive_summary=exec_summary or "Chưa có phân tích AI.",
            strengths=strengths,
            weaknesses=weaknesses,
            opportunities=opportunities,
            risks=risks,
            recommendation=_parse_recommendation(rec_text),
            confidence=_parse_confidence(conf_text),
            target_price=_parse_target_price(target_text),
            raw_response=content,
        )

    def _fallback_analysis(self, analysis: FinancialAnalysis) -> AIFinancialAnalysis:
        """Generate rule-based analysis when LLM is unavailable."""
        score = analysis.score
        strengths: list[str] = []
        risks: list[str] = []

        for sig in analysis.signals:
            if sig.level.value == "green":
                strengths.extend(sig.reasons)
            elif sig.level.value == "red":
                risks.extend(sig.reasons)

        latest = analysis.ratios[-1] if analysis.ratios else None
        summary_parts = [f"{analysis.company_name} đang duy trì"]
        if latest and latest.revenue_growth and latest.revenue_growth > 0:
            summary_parts.append("đà tăng trưởng tích cực,")
        if latest and latest.roe and latest.roe > Decimal("15"):
            summary_parts.append("khả năng sinh lời cao và")
        summary_parts.append("các chỉ số tài chính tương đối lành mạnh.")
        executive = " ".join(summary_parts)

        confidence = Decimal(str(min(99, max(50, int(float(score.overall_score) * 10)))))

        return AIFinancialAnalysis(
            symbol=analysis.symbol,
            executive_summary=executive,
            strengths=tuple(strengths[:5]),
            weaknesses=tuple(risks[:3]),
            opportunities=(),
            risks=tuple(risks[:5]),
            recommendation=score.recommendation,
            confidence=confidence,
            target_price=analysis.valuation.target_price,
        )
