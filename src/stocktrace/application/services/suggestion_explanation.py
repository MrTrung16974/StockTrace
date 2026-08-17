"""Safe LLM explanation of an existing deterministic investment suggestion."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from stocktrace.ai.suggestion_prompt_builder import SuggestionPromptBuilder
from stocktrace.domain.entities.investment_suggestion import InvestmentSuggestion
from stocktrace.domain.ports.llm_provider import LLMProvider
from stocktrace.infrastructure.config.settings import AISettings
from stocktrace.infrastructure.logging.config import get_logger

_DISALLOWED_ADVICE = re.compile(
    r"\b(mua\s+ngay|bán\s+ngay|ban\s+ngay|đặt\s+lệnh|dat\s+lenh|"
    r"all[ -]?in|tỷ\s+trọng|ty\s+trong|giá\s+mục\s+tiêu|gia\s+muc\s+tieu|"
    r"cắt\s+lỗ|cat\s+lo|chốt\s+lời|chot\s+loi|margin)\b",
    flags=re.IGNORECASE,
)
_MAX_EXPLANATION_LENGTH = 2500


class SuggestionExplanationStatus(StrEnum):
    """Whether the response was safely explained by AI or rendered from data."""

    AI_EXPLAINED = "AI_EXPLAINED"
    AI_REJECTED = "AI_REJECTED"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class SuggestionExplanation:
    """A presentation-only explanation paired with its deterministic suggestion."""

    suggestion: InvestmentSuggestion
    text: str
    status: SuggestionExplanationStatus


class SuggestionExplanationService:
    """Let an LLM explain verified facts without giving it decision authority."""

    def __init__(
        self,
        llm: LLMProvider | None,
        settings: AISettings,
        prompt_builder: SuggestionPromptBuilder | None = None,
    ) -> None:
        self._llm = llm
        self._settings = settings
        self._prompt_builder = prompt_builder or SuggestionPromptBuilder(
            max_tokens=settings.max_tokens,
            temperature=min(settings.temperature, 0.1),
        )
        self._logger = get_logger(__name__)

    @property
    def is_configured(self) -> bool:
        """Return whether a configured LLM may be asked to explain the suggestion."""
        return self._llm is not None and self._settings.enabled and self._settings.has_api_key

    async def explain(self, suggestion: InvestmentSuggestion) -> SuggestionExplanation:
        """Return a guarded AI explanation or a deterministic data-only fallback."""
        fallback = _render_data_only_explanation(suggestion)
        if not self.is_configured or self._llm is None:
            return SuggestionExplanation(
                suggestion=suggestion,
                text=fallback,
                status=SuggestionExplanationStatus.AI_UNAVAILABLE,
            )

        try:
            response = await self._llm.complete(self._prompt_builder.build(suggestion))
        except Exception as exc:
            self._logger.warning(
                "suggestion_explanation_failed",
                suggestion_id=suggestion.suggestion_id,
                error=str(exc),
            )
            return SuggestionExplanation(
                suggestion=suggestion,
                text=fallback,
                status=SuggestionExplanationStatus.AI_UNAVAILABLE,
            )

        text = response.content.strip()
        if not _is_safe_explanation(text, suggestion):
            self._logger.warning(
                "suggestion_explanation_rejected",
                suggestion_id=suggestion.suggestion_id,
            )
            return SuggestionExplanation(
                suggestion=suggestion,
                text=fallback,
                status=SuggestionExplanationStatus.AI_REJECTED,
            )
        return SuggestionExplanation(
            suggestion=suggestion,
            text=text,
            status=SuggestionExplanationStatus.AI_EXPLAINED,
        )


def _is_safe_explanation(text: str, suggestion: InvestmentSuggestion) -> bool:
    """Reject output that tries to turn explanation into an investing instruction."""
    if not text or len(text) > _MAX_EXPLANATION_LENGTH or _DISALLOWED_ADVICE.search(text):
        return False
    normalized = text.casefold()
    if suggestion.action.value.casefold() not in normalized:
        return False
    tokens = set(re.findall(r"[a-z0-9_]+", normalized))
    required_evidence = {item.factor_code.casefold() for item in suggestion.evidence}
    required_invalidations = {
        item.code.casefold() for item in suggestion.invalidation_conditions
    }
    return required_evidence.issubset(tokens) and required_invalidations.issubset(tokens)


def _render_data_only_explanation(suggestion: InvestmentSuggestion) -> str:
    """Render a complete explanation without generating a new investment conclusion."""
    evidence = "; ".join(
        f"{item.factor_code}: {item.label} = {item.value} ({item.source})"
        for item in suggestion.evidence
    )
    invalidations = "; ".join(
        f"{item.code}: {item.description}" for item in suggestion.invalidation_conditions
    )
    return "\n".join(
        [
            f"Action đã được Rule Engine xác định: {suggestion.action.value}.",
            f"Mã: {suggestion.symbol}; kỳ hạn: {suggestion.horizon.value}; "
            f"rủi ro: {suggestion.risk_level.value}; confidence: {suggestion.confidence}.",
            f"Bằng chứng đã xác minh: {evidence}.",
            f"Điều kiện vô hiệu: {invalidations}.",
            suggestion.disclaimer,
        ],
    )
