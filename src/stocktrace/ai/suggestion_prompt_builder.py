"""Constrained LLM prompt for explaining an already-determined suggestion."""

from __future__ import annotations

import json

from stocktrace.ai.models import LLMRequest
from stocktrace.domain.entities.investment_suggestion import InvestmentSuggestion

_SYSTEM_PROMPT = """Bạn là bộ chuyển ngữ cho một quyết định đã được Rule Engine xác định.
Bạn KHÔNG phải là người ra quyết định đầu tư. Chỉ diễn giải dữ liệu được cung cấp.
Không được thay đổi action, symbol, mức rủi ro, confidence, evidence, điều kiện vô hiệu,
không được đưa giá, khối lượng, tỷ trọng, thời điểm mua/bán hoặc hướng dẫn đặt lệnh.
Nếu thông tin không có trong input, hãy nói rõ là không có trong input.
Không cam kết lợi nhuận. Trả lời bằng tiếng Việt, tối đa 180 từ."""


class SuggestionPromptBuilder:
    """Serialize only verified suggestion fields into a constrained LLM request."""

    def __init__(self, *, max_tokens: int = 500, temperature: float = 0.1) -> None:
        self._max_tokens = max_tokens
        self._temperature = temperature

    def build(self, suggestion: InvestmentSuggestion) -> LLMRequest:
        """Build a prompt that allows explanation but forbids investment decisions."""
        facts = {
            "action": suggestion.action.value,
            "confidence": str(suggestion.confidence),
            "evidence": [
                {
                    "factor_code": item.factor_code,
                    "label": item.label,
                    "source": item.source,
                    "value": item.value,
                }
                for item in suggestion.evidence
            ],
            "horizon": suggestion.horizon.value,
            "invalidation_conditions": [
                {"code": item.code, "description": item.description}
                for item in suggestion.invalidation_conditions
            ],
            "risk_level": suggestion.risk_level.value,
            "rule_version": suggestion.rule_version,
            "symbol": suggestion.symbol,
        }
        prompt = "\n".join(
            [
                "Hãy diễn giải bằng ngôn ngữ dễ hiểu đúng các facts JSON sau:",
                json.dumps(facts, ensure_ascii=False, sort_keys=True),
                "Yêu cầu trả lời:",
                "- Nêu action nguyên văn, sau đó giải thích evidence và điều kiện vô hiệu.",
                "- Không thêm bất kỳ kết luận, dữ kiện hay hành động nào ngoài JSON.",
                "- Không dùng các chỉ dẫn như 'mua ngay', 'bán ngay', 'đặt lệnh', 'khối lượng', "
                "'giá mục tiêu', 'cắt lỗ', 'chốt lời', 'tỷ trọng' hoặc 'margin'.",
                "- Kết thúc bằng: 'Thông tin chỉ nhằm mục đích tham khảo.'",
            ],
        )
        return LLMRequest(
            prompt=prompt,
            max_tokens=min(self._max_tokens, 500),
            temperature=self._temperature,
            system_prompt=_SYSTEM_PROMPT,
        )
