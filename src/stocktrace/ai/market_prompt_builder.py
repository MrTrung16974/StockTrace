"""Prompt construction for market analysis."""

from __future__ import annotations

from stocktrace.ai.models import LLMRequest, MarketAnalysisContext
from stocktrace.application.services.market_data import NewsArticle, StockQuote

_SYSTEM_PROMPT = (
    "Bạn là chuyên gia phân tích vĩ mô và thị trường tài chính Việt Nam. "
    "Trả lời chính xác theo định dạng section được yêu cầu."
)

_SUMMARY_MAX_CHARS = 200


class MarketPromptBuilder:
    """Build standardized Vietnamese prompts for market analysis."""

    def __init__(self, max_tokens: int = 1500, temperature: float = 0.3) -> None:
        self._max_tokens = max_tokens
        self._temperature = temperature

    def build(self, context: MarketAnalysisContext) -> LLMRequest:
        """Build a prompt from gathered market context."""
        prompt = self._build_prompt(context)

        return LLMRequest(
            prompt=prompt,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            system_prompt=_SYSTEM_PROMPT,
        )

    def _build_prompt(self, context: MarketAnalysisContext) -> str:
        indices_block = self._format_quotes_block(context.indices, "Chỉ số")
        sectors_block = self._format_quotes_block(context.sectors, "Nhóm ngành (Cổ phiếu đại diện)")
        international_block = self._format_quotes_block(context.international, "Dữ liệu quốc tế")
        news_block = self._format_news_block(context.news)

        lines = [
            "Bạn là chuyên gia phân tích vĩ mô và thị trường tài chính Việt Nam.",
            "",
            "Hãy phân tích tổng quan thị trường dựa trên dữ liệu sau:",
            "",
            indices_block,
            "",
            sectors_block,
            "",
            international_block,
            "",
            "Tin tức kinh tế mới nhất:",
            news_block,
            "",
            "Yêu cầu:",
            "- Trả lời bằng tiếng Việt chuyên nghiệp, giọng văn của chuyên gia.",
            "- BẮT BUỘC Dùng đúng các header sau (mỗi header trên một dòng riêng):",
            "[TỔNG QUAN]",
            "[TÂM LÝ THỊ TRƯỜNG]",
            "[NHÓM NGÀNH TÍCH CỰC]",
            "[NHÓM NGÀNH TIÊU CỰC]",
            "[DÒNG TIỀN]",
            "[ẢNH HƯỞNG QUỐC TẾ]",
            "[NHẬN ĐỊNH NGẮN HẠN]",
            "[NHẬN ĐỊNH TRUNG HẠN]",
            "[RỦI RO CẦN THEO DÕI]",
            "[KẾT LUẬN]",
            "- Tại [NHÓM NGÀNH TÍCH CỰC] và [NHÓM NGÀNH TIÊU CỰC], chỉ liệt kê tên nhóm ngành (ví dụ: Ngân hàng, Công nghệ).",
            "- Không cam kết lợi nhuận hay đưa ra lời khuyên đầu tư tuyệt đối.",
        ]
        return "\n".join(lines)

    def _format_quotes_block(self, quotes: dict[str, StockQuote | None], label: str) -> str:
        lines = [f"{label}:"]
        for key, quote in quotes.items():
            if quote is None:
                lines.append(f"- {key}: Không có dữ liệu")
                continue
            change_prefix = "+" if quote.change_percent > 0 else ""
            lines.append(f"- {key}: {quote.current_price} ({change_prefix}{quote.change_percent}%)")
        if len(lines) == 1:
            lines.append("- Không có dữ liệu")
        return "\n".join(lines)

    def _format_news_block(self, articles: tuple[NewsArticle, ...]) -> str:
        if not articles:
            return "Không có tin tức mới."

        lines: list[str] = []
        for index, article in enumerate(articles, start=1):
            summary = (article.summary or "").strip()
            if len(summary) > _SUMMARY_MAX_CHARS:
                summary = f"{summary[:_SUMMARY_MAX_CHARS].rstrip()}..."
            summary_line = f"   Mô tả: {summary}" if summary else ""
            lines.append(f"{index}. {article.title}")
            if summary_line:
                lines.append(summary_line)
            lines.append(f"   Nguồn: {article.source}")
        return "\n".join(lines)
