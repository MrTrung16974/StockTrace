"""Professional Telegram report formatters for stock analysis."""

from __future__ import annotations

from decimal import Decimal
from html import escape

from stocktrace.ai.models import StockAnalysisResult
from stocktrace.application.services.liquidity_analysis_service import LiquidityAssessment
from stocktrace.application.services.market_data import StockQuote
from stocktrace.application.services.news_analysis_service import NewsSentimentResult
from stocktrace.application.services.stock_analysis_service import AnalysisBundle
from stocktrace.application.services.stock_score_service import StockScore
from stocktrace.application.services.technical_analysis_service import TechnicalIndicators


def build_professional_analysis_report(bundle: AnalysisBundle) -> str:
    """Build a detailed brokerage-style analysis report (HTML parse mode)."""
    symbol = escape(bundle.symbol)
    sections: list[str] = [
        f"📊 <b>PHÂN TÍCH CỔ PHIẾU {symbol}</b>",
        f"<i>Báo cáo AI • {bundle.symbol}</i>",
        "",
        _format_price_section(bundle.quote),
    ]

    if bundle.technical is not None:
        sections.extend(["", _format_technical_section(bundle.technical)])

    if bundle.fundamentals:
        sections.extend(["", _format_fundamental_section(bundle.fundamentals, bundle.fundamental_raw)])

    if bundle.liquidity is not None:
        sections.extend(["", _format_liquidity_section(bundle.liquidity)])

    if bundle.news_sentiment is not None and bundle.news:
        sections.extend(["", _format_news_section(bundle.news_sentiment, bundle.news)])

    if bundle.score is not None:
        sections.extend(["", _format_score_section(bundle.score)])

    if bundle.analysis is not None:
        sections.extend(["", _format_ai_section(bundle.analysis)])

    sections.append("")
    sections.append("<i>⚠️ Báo cáo tham khảo, không phải khuyến nghị đầu tư.</i>")
    return "\n".join(sections)


def _format_price_section(quote: StockQuote | None) -> str:
    if quote is None:
        return "💰 <b>Giá &amp; Biến động</b>\nKhông có dữ liệu giá."
    trend = _trend_label(quote.change_percent)
    sign = "+" if quote.change_percent > 0 else ""
    return "\n".join(
        [
            "💰 <b>Giá &amp; Biến động</b>",
            f"• Giá hiện tại: <b>{_format_vn_price(quote.current_price)}</b> {escape(quote.currency)}",
            f"• Thay đổi: {sign}{_format_decimal(quote.change_percent)}%",
            f"• Xu hướng ngày: <b>{trend}</b>",
            f"• Cao/Thấp: {_format_vn_price(quote.high_price)} / {_format_vn_price(quote.low_price)}",
            f"• Khối lượng: {quote.volume:,}".replace(",", "."),
        ],
    )


def _format_technical_section(tech: TechnicalIndicators) -> str:
    lines = [
        "📈 <b>Phân tích Kỹ thuật (TA)</b>",
        f"• RSI(14): {tech.rsi or 'N/A'}",
        f"• MACD: {tech.macd or 'N/A'} | Signal: {tech.macd_signal or 'N/A'} | Hist: {tech.macd_hist or 'N/A'}",
        f"• EMA20: {tech.ema20 or 'N/A'} | EMA50: {tech.ema50 or 'N/A'} | EMA200: {tech.ema200 or 'N/A'}",
        f"• Bollinger: Trên {tech.bb_upper or 'N/A'} | Giữa {tech.bb_middle or 'N/A'} | Dưới {tech.bb_lower or 'N/A'}",
        f"• Xu hướng: Ngắn hạn <b>{tech.short_term_trend}</b> | TB <b>{tech.mid_term_trend}</b> | Dài hạn <b>{tech.long_term_trend}</b>",
        f"• Hỗ trợ: {tech.support or 'N/A'} | Kháng cự: {tech.resistance or 'N/A'}",
        f"• Tín hiệu TA: <b>{tech.signal}</b>",
    ]
    return "\n".join(lines)


def _format_fundamental_section(fundamentals: dict[str, str], raw) -> str:
    lines = ["🏦 <b>Phân tích Cơ bản (FA)</b>"]
    for metric, rating in fundamentals.items():
        lines.append(f"• {metric}: <b>{escape(rating)}</b>")
    if raw is not None:
        if raw.pe is not None:
            lines.append(f"• PE thực tế: {raw.pe}")
        if raw.pb is not None:
            lines.append(f"• PB thực tế: {raw.pb}")
        if raw.eps is not None:
            lines.append(f"• EPS: {raw.eps}")
        if raw.roe is not None:
            lines.append(f"• ROE: {raw.roe}%")
    return "\n".join(lines)


def _format_liquidity_section(liquidity: LiquidityAssessment) -> str:
    net_text = "N/A"
    if liquidity.foreign_net_vol is not None:
        sign = "+" if liquidity.foreign_net_vol > 0 else ""
        net_text = f"{sign}{liquidity.foreign_net_vol:,}".replace(",", ".")
    return "\n".join(
        [
            "💧 <b>Thanh khoản &amp; Dòng tiền</b>",
            f"• Trạng thái: <b>{escape(liquidity.status)}</b>",
            f"• KL hiện tại / TB20: {liquidity.current_volume:,} / {liquidity.avg_volume_20d:,}".replace(",", "."),
            f"• Tỷ lệ KL: {liquidity.volume_ratio}x",
            f"• {escape(liquidity.foreign_flow_label)}",
            f"• Khối ngoại ròng: {net_text}",
        ],
    )


def _format_news_section(sentiment: NewsSentimentResult, news: tuple) -> str:
    lines = [
        "📰 <b>Tin tức &amp; Sentiment</b>",
        f"• Đánh giá: <b>{escape(sentiment.label)}</b> "
        f"(+{sentiment.positive_count} / −{sentiment.negative_count} / ={sentiment.neutral_count})",
    ]
    for index, article in enumerate(news[:5], start=1):
        title = escape(article.title)
        url = escape(article.url)
        lines.append(f'{index}. <a href="{url}">{title}</a>')
    return "\n".join(lines)


def _format_score_section(score: StockScore) -> str:
    return "\n".join(
        [
            "⭐ <b>Điểm số AI</b>",
            f"• Tổng thể: <b>{score.overall_score}/100</b> {score.stars}",
            f"• Kỹ thuật: {score.technical_score} | Cơ bản: {score.fundamental_score}",
            f"• Tin tức: {score.news_score} | Momentum: {score.momentum_score}",
        ],
    )


def _format_ai_section(analysis: StockAnalysisResult) -> str:
    lines = [
        "🤖 <b>NHẬN ĐỊNH AI</b>",
        "",
        f"<b>Tổng quan</b>\n{escape(analysis.overview)}",
        "",
        f"<b>Điểm mạnh</b>\n{escape(analysis.positives)}",
        "",
        f"<b>Rủi ro</b>\n{escape(analysis.risks)}",
        "",
        f"<b>Ngắn hạn</b>\n{escape(analysis.short_term)}",
    ]
    if analysis.medium_term:
        lines.extend(["", f"<b>Trung hạn</b>\n{escape(analysis.medium_term)}"])
    if analysis.positive_scenario:
        lines.extend(["", f"<b>Kịch bản tích cực</b>\n{escape(analysis.positive_scenario)}"])
    if analysis.neutral_scenario:
        lines.extend(["", f"<b>Kịch bản trung lập</b>\n{escape(analysis.neutral_scenario)}"])
    if analysis.negative_scenario:
        lines.extend(["", f"<b>Kịch bản tiêu cực</b>\n{escape(analysis.negative_scenario)}"])
    if analysis.recommendation_action:
        confidence = analysis.recommendation_confidence or "N/A"
        lines.extend(
            [
                "",
                f"<b>Khuyến nghị</b>: <b>{escape(analysis.recommendation_action)}</b> "
                f"(Độ tin cậy: {escape(confidence)})",
            ],
        )
        if analysis.recommendation_reasons:
            lines.append(escape(analysis.recommendation_reasons))
    if analysis.conclusion:
        lines.extend(["", f"<b>Kết luận</b>\n{escape(analysis.conclusion)}"])
    return "\n".join(lines)


def _trend_label(change_percent: Decimal) -> str:
    if change_percent > 0:
        return "Tăng"
    if change_percent < 0:
        return "Giảm"
    return "Đi ngang"


def _format_decimal(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01")) if value.as_tuple().exponent < -2 else value
    prefix = "+" if value > 0 else ""
    return f"{prefix}{normalized:,}".replace(",", ".")


def _format_vn_price(value: Decimal) -> str:
    if value == value.to_integral():
        return f"{int(value):,}".replace(",", ".")
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
