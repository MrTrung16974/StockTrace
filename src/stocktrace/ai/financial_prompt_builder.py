"""Prompt builder for financial analysis."""

from __future__ import annotations

from stocktrace.ai.financial_models import FinancialAnalysisContext


class FinancialPromptBuilder:
    """Build LLM prompts for financial statement analysis."""

    SYSTEM_PROMPT = (
        "You are a senior equity research analyst specializing in Vietnamese stocks. "
        "Provide concise, actionable financial analysis in Vietnamese. "
        "Use bullet points for strengths, weaknesses, opportunities, and risks."
    )

    def build(self, context: FinancialAnalysisContext) -> str:
        """Build analysis prompt from financial context."""
        ratio_lines = "\n".join(f"- {k}: {v}" for k, v in context.ratios_summary.items())
        val_lines = "\n".join(f"- {k}: {v}" for k, v in context.valuation_summary.items())
        strength_hints = "\n".join(f"- {s}" for s in context.strengths_hints)
        risk_hints = "\n".join(f"- {r}" for r in context.risks_hints)

        return f"""Analyze the financial health of {context.company_name} ({context.symbol})
for period {context.period_label}.

Financial Score: {context.score.overall_score}/10
Recommendation: {context.score.recommendation.value}

Key Ratios:
{ratio_lines}

Valuation:
{val_lines}

Detected Strengths:
{strength_hints}

Detected Risks:
{risk_hints}

Provide your analysis in this exact format:

EXECUTIVE_SUMMARY:
[2-3 sentence summary]

STRENGTHS:
- [strength 1]
- [strength 2]

WEAKNESSES:
- [weakness 1]

OPPORTUNITIES:
- [opportunity 1]

RISKS:
- [risk 1]

RECOMMENDATION:
[BUY/SELL/HOLD/STRONG BUY/STRONG SELL]

CONFIDENCE:
[0-100]%

TARGET_PRICE:
[price in VND or N/A]
"""
