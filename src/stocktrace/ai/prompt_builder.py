"""Prompt construction for stock analysis."""

from __future__ import annotations

from decimal import Decimal

from stocktrace.ai.models import AnalysisContext, AnalysisMode, LLMRequest
from stocktrace.application.services.market_data import NewsArticle, StockQuote

_SYSTEM_PROMPT = (
    "Bạn là chuyên gia phân tích chứng khoán Việt Nam. "
    "Trả lời chính xác theo định dạng section được yêu cầu."
)

_SUMMARY_MAX_CHARS = 200


class PromptBuilder:
    """Build standardized Vietnamese prompts for stock analysis."""

    def __init__(self, max_tokens: int = 1024, temperature: float = 0.3) -> None:
        self._max_tokens = max_tokens
        self._temperature = temperature

    def build(self, context: AnalysisContext) -> LLMRequest:
        """Build a prompt from gathered market context."""
        if context.mode == AnalysisMode.NEWS_ONLY:
            prompt = self._build_news_only_prompt(context)
            max_tokens = min(self._max_tokens, 768)
        else:
            prompt = self._build_full_prompt(context)
            max_tokens = self._max_tokens

        return LLMRequest(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=self._temperature,
            system_prompt=_SYSTEM_PROMPT,
        )

    def _build_news_only_prompt(self, context: AnalysisContext) -> str:
        price_block = self._format_price_block(context.price)
        news_block = self._format_news_block(context.news)

        return "\n".join(
            [
                "Bạn là chuyên gia phân tích chứng khoán Việt Nam.",
                "",
                f"Hãy phân tích mã cổ phiếu: {context.symbol}",
                "",
                price_block,
                "",
                "Tin tức:",
                news_block,
                "",
                "Yêu cầu:",
                "- Trả lời bằng tiếng Việt.",
                "- Không quá 250 từ.",
                "- Dùng đúng các header sau (mỗi header trên một dòng riêng):",
                "[TỔNG QUAN]",
                "[ĐIỂM TÍCH CỰC]",
                "[RỦI RO]",
                "[ĐÁNH GIÁ NGẮN HẠN]",
                "- Không cam kết lợi nhuận.",
                "- Không khuyến nghị mua bán tuyệt đối.",
            ],
        )

    def _build_full_prompt(self, context: AnalysisContext) -> str:
        price_block = self._format_price_block(context.price)
        news_block = self._format_news_block(context.news)
        historical_block = self._format_historical_block(context.historical)
        
        tech_block = "Không có dữ liệu"
        if context.technical_indicators:
            t = context.technical_indicators
            tech_block = (
                f"- RSI: {t.get('rsi')}\n"
                f"- MACD: {t.get('macd')} (Signal: {t.get('macd_signal')}, Hist: {t.get('macd_hist')})\n"
                f"- EMA20: {t.get('ema20')} | EMA50: {t.get('ema50')} | EMA200: {t.get('ema200')}\n"
                f"- Bollinger Bands: Upper {t.get('bb_upper')}, Lower {t.get('bb_lower')}\n"
                f"- Xu hướng: Ngắn hạn ({t.get('short_term_trend')}), Trung hạn ({t.get('mid_term_trend')}), Dài hạn ({t.get('long_term_trend')})\n"
                f"- Hỗ trợ: {t.get('support')} | Kháng cự: {t.get('resistance')}\n"
                f"- Tín hiệu: {t.get('signal')}"
            )
            
        fund_block = "Không có dữ liệu"
        if context.fundamental_data:
            fund_block = "\n".join(f"- {k}: {v}" for k, v in context.fundamental_data.items())

        score_block = ""
        if context.score:
            score_block = (
                f"Điểm tổng thể: {context.score.get('overall_score')}/100 "
                f"({context.score.get('stars')})\n"
                f"Kỹ thuật: {context.score.get('technical_score')} | "
                f"Cơ bản: {context.score.get('fundamental_score')} | "
                f"Tin tức: {context.score.get('news_score')} | "
                f"Momentum: {context.score.get('momentum_score')}"
            )

        lines = [
            "Bạn là chuyên gia phân tích chứng khoán Việt Nam cấp cao.",
            "",
            f"Hãy phân tích mã cổ phiếu: {context.symbol}",
            "",
            price_block,
            "",
            "Phân tích Kỹ thuật:",
            tech_block,
            "",
            "Phân tích Cơ bản:",
            fund_block,
            "",
            "Điểm số AI:",
            score_block or "Không có dữ liệu",
            "",
            "Tin tức mới nhất:",
            news_block,
        ]

        lines.extend(
            [
                "",
                "Yêu cầu:",
                "- Trả lời bằng tiếng Việt chuyên nghiệp.",
                "- Không quá 800 từ.",
                "- BẮT BUỘC Dùng đúng các header sau (mỗi header trên một dòng riêng):",
                "[TỔNG QUAN]",
                "[ĐIỂM TÍCH CỰC]",
                "[RỦI RO]",
                "[ĐÁNH GIÁ NGẮN HẠN]",
                "[ĐÁNH GIÁ TRUNG HẠN]",
                "[KỊCH BẢN TÍCH CỰC]",
                "[KỊCH BẢN TRUNG LẬP]",
                "[KỊCH BẢN TIÊU CỰC]",
                "[KHUYẾN NGHỊ]",
                "- Header [KHUYẾN NGHỊ] phải bao gồm hành động (MUA/BÁN/GIỮ/QUAN SÁT), độ tin cậy %, và 3 lý do chính.",
            ],
        )
        return "\n".join(lines)

    def _format_price_block(self, quote: StockQuote | None) -> str:
        if quote is None:
            return "Giá hiện tại: Không có dữ liệu\nBiến động: Không có dữ liệu"

        change_prefix = "+" if quote.change_percent > 0 else ""
        trend = _trend_label(quote.change_percent)
        return "\n".join(
            [
                f"Giá hiện tại: {quote.current_price}",
                f"Biến động: {change_prefix}{quote.change_percent}%",
                f"Xu hướng: {trend}",
            ],
        )

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

    def _format_historical_block(self, points: tuple[object, ...]) -> str:
        if not points:
            return ""
        lines: list[str] = []
        for point in points:
            day = getattr(point, "day", None)
            close = getattr(point, "close", None)
            change_percent = getattr(point, "change_percent", None)
            if day is None or close is None:
                continue
            prefix = "+" if isinstance(change_percent, Decimal) and change_percent > 0 else ""
            change_text = (
                f"{prefix}{change_percent}%"
                if isinstance(change_percent, Decimal)
                else "n/a"
            )
            lines.append(f"- {day}: {close} ({change_text})")
        return "\n".join(lines)


def _trend_label(change_percent: Decimal) -> str:
    if change_percent > 0:
        return "Tăng"
    if change_percent < 0:
        return "Giảm"
    return "Đi ngang"
