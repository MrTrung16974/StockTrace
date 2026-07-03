"""Professional Telegram report formatters for stock analysis."""

from __future__ import annotations

from decimal import Decimal
from html import escape

from stocktrace.ai.models import StockAnalysisResult
from stocktrace.application.services.market_analysis_service import MarketAnalysisBundle
from stocktrace.application.services.market_data import HistoricalPrice, NewsArticle, StockQuote
from stocktrace.application.services.news_analysis_service import NewsSentimentResult
from stocktrace.application.services.stock_analysis_service import AnalysisBundle
from stocktrace.application.services.stock_score_service import StockScore
from stocktrace.application.services.technical_analysis_service import TechnicalIndicators

_DIVIDER = "━━━━━━━━━━━━━━"
_NA = "Chưa có dữ liệu"

_PERIOD_DAYS = {
    "week": 5,
    "month": 21,
    "quarter": 63,
    "half_year": 126,
    "year": 252,
}

_RANKING_LEVELS = (
    (90, "⭐⭐⭐⭐⭐ Mạnh"),
    (80, "⭐⭐⭐⭐ Tích cực"),
    (70, "⭐⭐⭐ Trung lập"),
    (60, "⭐⭐ Yếu"),
    (0, "⭐ Rủi ro cao"),
)


def build_professional_analysis_report(bundle: AnalysisBundle) -> str:
    """Build a detailed brokerage-style analysis report (HTML parse mode)."""
    symbol = escape(bundle.symbol)
    sections: list[str] = [
        f"📊 <b>BÁO CÁO PHÂN TÍCH CỔ PHIẾU {symbol}</b>",
        "",
        _DIVIDER,
        "",
        _format_company_section(bundle),
        "",
        _DIVIDER,
        "",
        _format_current_price_section(bundle.quote),
        "",
        _DIVIDER,
        "",
        _format_price_performance_section(bundle),
        "",
        _DIVIDER,
        "",
        _format_technical_section(bundle.technical, bundle.quote, bundle.liquidity),
        "",
        _DIVIDER,
        "",
        _format_flow_section(bundle.liquidity),
        "",
        _DIVIDER,
        "",
        _format_news_impact_section(bundle.news, bundle.news_sentiment),
        "",
        _DIVIDER,
        "",
        _format_fundamental_section(bundle.fundamental_raw, bundle.fundamentals),
        "",
        _DIVIDER,
        "",
        _format_ai_score_section(bundle.score, bundle.analysis),
        "",
        _DIVIDER,
        "",
        _format_price_scenario_section(bundle.technical, bundle.analysis),
        "",
        _DIVIDER,
        "",
        _format_recommendation_section(bundle.analysis, bundle.score, bundle.technical),
        "",
        "⚠️ Đây không phải khuyến nghị đầu tư. Nhà đầu tư cần tự chịu trách nhiệm với quyết định của mình.",
    ]
    return "\n".join(sections)


def build_market_analysis_report(bundle: MarketAnalysisBundle) -> str:
    """Build a detailed market analysis report."""
    timestamp = bundle.timestamp.astimezone().strftime("%d/%m/%Y %H:%M")
    sections = [
        "📊 <b>BÁO CÁO THỊ TRƯỜNG TÀI CHÍNH VIỆT NAM</b>",
        "",
        f"Cập nhật: {timestamp}",
        "",
        _DIVIDER,
        "",
        "🇻🇳 <b>THỊ TRƯỜNG TRONG NƯỚC</b>",
        "",
    ]
    
    # Indices
    for name, quote in bundle.indices.items():
        if quote:
            change = _format_signed_decimal(quote.change_percent)
            sections.append(f"<b>{name}</b>: {_format_vn_price(quote.current_price)} ({change}%)")
        else:
            sections.append(f"<b>{name}</b>: {_NA}")
    sections.append("")

    if bundle.analysis:
        analysis = bundle.analysis
        sections.extend([
            _DIVIDER,
            "",
            "🤖 <b>PHÂN TÍCH AI</b>",
            "",
            _field("Tổng quan", escape(analysis.overview)),
            "",
            _field("Tâm lý thị trường", escape(analysis.sentiment.value.upper())),
            "",
            "Nhóm ngành tích cực:",
            f"✅ {escape(analysis.positive_sectors)}",
            "",
            "Nhóm ngành tiêu cực:",
            f"⚠️ {escape(analysis.negative_sectors)}",
            "",
            _field("Dòng tiền", escape(analysis.cash_flow)),
            "",
            _DIVIDER,
            "",
            "🌎 <b>ẢNH HƯỞNG QUỐC TẾ</b>",
            "",
            escape(analysis.international_impact),
            "",
            _DIVIDER,
            "",
            "📈 <b>NHẬN ĐỊNH NGẮN HẠN</b>",
            "",
            escape(analysis.short_term),
            "",
            _DIVIDER,
            "",
            "📊 <b>NHẬN ĐỊNH TRUNG HẠN</b>",
            "",
            escape(analysis.medium_term),
            "",
            _DIVIDER,
            "",
            "⚠️ <b>RỦI RO CẦN THEO DÕI</b>",
            "",
            escape(analysis.risks),
            "",
            _DIVIDER,
            "",
            "🎯 <b>KẾT LUẬN</b>",
            "",
            escape(analysis.conclusion),
        ])
    else:
        sections.append("Không có phân tích AI.")

    return "\n".join(sections)


def _format_company_section(bundle: AnalysisBundle) -> str:
    quote = bundle.quote
    company_name = escape(quote.company_name) if quote else _NA
    return "\n".join(
        [
            "🏢 <b>THÔNG TIN DOANH NGHIỆP</b>",
            "",
            _field("Mã", escape(bundle.symbol)),
            "",
            _field("Tên doanh nghiệp", company_name),
            "",
            _field("Ngành", _NA),
            "",
            _field("Vốn hóa", _NA),
        ],
    )


def _format_current_price_section(quote: StockQuote | None) -> str:
    if quote is None:
        return "\n".join(
            [
                "💰 <b>GIÁ HIỆN TẠI</b>",
                "",
                _field("Giá", _NA),
                "",
                _field("Thay đổi", _NA),
                "",
                _field("Khối lượng", _NA),
                "",
                _field("GTGD", _NA),
                "",
                _field("Giá mở cửa", _NA),
                "",
                _field("Cao nhất", _NA),
                "",
                _field("Thấp nhất", _NA),
            ],
        )

    change = _format_signed_decimal(quote.change_percent)
    trading_value = _format_trading_value(quote.current_price, quote.volume)
    return "\n".join(
        [
            "💰 <b>GIÁ HIỆN TẠI</b>",
            "",
            _field("Giá", _format_vn_price(quote.current_price)),
            "",
            _field("Thay đổi", f"{change}%"),
            "",
            _field("Khối lượng", _format_volume(quote.volume)),
            "",
            _field("GTGD", trading_value),
            "",
            _field("Giá mở cửa", _format_vn_price(quote.open_price)),
            "",
            _field("Cao nhất", _format_vn_price(quote.high_price)),
            "",
            _field("Thấp nhất", _format_vn_price(quote.low_price)),
        ],
    )


def _format_price_performance_section(bundle: AnalysisBundle) -> str:
    quote = bundle.quote
    day_change = _format_signed_decimal(quote.change_percent) if quote else _NA
    history = bundle.price_history

    def period_change(days: int) -> str:
        if quote is None or not history:
            return _NA
        value = _calculate_period_change(history, quote.current_price, days)
        if value is None:
            return _NA
        return f"{_format_signed_decimal(value)}%"

    performance_comment = _performance_comment(quote, history)
    return "\n".join(
        [
            "📈 <b>HIỆU SUẤT GIÁ</b>",
            "",
            _field("Trong ngày", f"{day_change}%" if day_change != _NA else _NA),
            "",
            _field("1 tuần", period_change(_PERIOD_DAYS["week"])),
            "",
            _field("1 tháng", period_change(_PERIOD_DAYS["month"])),
            "",
            _field("3 tháng", period_change(_PERIOD_DAYS["quarter"])),
            "",
            _field("6 tháng", period_change(_PERIOD_DAYS["half_year"])),
            "",
            _field("1 năm", period_change(_PERIOD_DAYS["year"])),
            "",
            _field("So với VNINDEX", _NA),
            "",
            _field("Đánh giá", performance_comment),
        ],
    )


def _format_technical_section(
    tech: TechnicalIndicators | None,
    quote: StockQuote | None,
    liquidity: LiquidityAssessment | None = None,
) -> str:
    if tech is None:
        return "\n".join(
            [
                "📊 <b>PHÂN TÍCH KỸ THUẬT</b>",
                "",
                _field("Xu hướng ngắn hạn", _NA),
                "",
                _field("Xu hướng trung hạn", _NA),
                "",
                _field("Xu hướng dài hạn", _NA),
                "",
                _field("EMA20", _NA),
                "",
                _field("EMA50", _NA),
                "",
                _field("EMA200", _NA),
                "",
                _field("RSI", _NA),
                "",
                _field("MACD", _NA),
                "",
                _field("Bollinger Band", _NA),
                "",
                _field("Khối lượng", _NA),
                "",
                _field("Hỗ trợ gần", _NA),
                "",
                _field("Kháng cự gần", _NA),
            ],
        )

    current_price = quote.current_price if quote else None
    return "\n".join(
        [
            "📊 <b>PHÂN TÍCH KỸ THUẬT</b>",
            "",
            _field("Xu hướng ngắn hạn", tech.short_term_trend),
            "",
            _field("Xu hướng trung hạn", tech.mid_term_trend),
            "",
            _field("Xu hướng dài hạn", tech.long_term_trend),
            "",
            _field("EMA20", _ema_status(current_price, tech.ema20)),
            "",
            _field("EMA50", _ema_status(current_price, tech.ema50)),
            "",
            _field("EMA200", _ema_status(current_price, tech.ema200)),
            "",
            _field("RSI", _rsi_status(tech.rsi)),
            "",
            _field("MACD", _macd_status(tech)),
            "",
            _field("Bollinger Band", _bollinger_status(current_price, tech)),
            "",
            _field("Khối lượng", _volume_analysis_label(liquidity)),
            "",
            _field("Hỗ trợ gần", _format_vn_price(tech.support) if tech.support else _NA),
            "",
            _field("Kháng cự gần", _format_vn_price(tech.resistance) if tech.resistance else _NA),
        ],
    )


def _format_flow_section(liquidity: LiquidityAssessment | None) -> str:
    if liquidity is None:
        return "\n".join(
            [
                "💵 <b>PHÂN TÍCH DÒNG TIỀN</b>",
                "",
                _field("Khối ngoại", _NA),
                "",
                _field("Tự doanh", _NA),
                "",
                _field("Dòng tiền lớn", _NA),
                "",
                _field("Thanh khoản", _NA),
                "",
                _field("Đánh giá", _NA),
            ],
        )

    foreign_flow = _format_foreign_flow(liquidity)
    flow_comment = f"{liquidity.foreign_flow_label}. {liquidity.status}."
    return "\n".join(
        [
            "💵 <b>PHÂN TÍCH DÒNG TIỀN</b>",
            "",
            _field("Khối ngoại", foreign_flow),
            "",
            _field("Tự doanh", _NA),
            "",
            _field("Dòng tiền lớn", _NA),
            "",
            _field("Thanh khoản", liquidity.status),
            "",
            _field("Đánh giá", flow_comment),
        ],
    )


def _format_news_impact_section(
    news: tuple[NewsArticle, ...],
    sentiment: NewsSentimentResult | None,
) -> str:
    lines = ["📰 <b>TIN TỨC TÁC ĐỘNG</b>", ""]
    selected = news[:3]
    if not selected:
        lines.extend(
            [
                "1.",
                "",
                _NA,
                "",
                _field("Tác động", _NA),
            ],
        )
        return "\n".join(lines)

    for index, article in enumerate(selected, start=1):
        title = escape(article.title)
        impact = _news_impact_label(article)
        lines.extend(
            [
                f"{index}.",
                "",
                title,
                "",
                _field("Tác động", impact),
                "",
            ],
        )
    return "\n".join(lines).rstrip()


def _format_fundamental_section(
    raw,
    fundamentals: dict[str, str] | None,
) -> str:
    pe = _format_metric(raw.pe if raw else None)
    pb = _format_metric(raw.pb if raw else None)
    eps = _format_metric(raw.eps if raw else None)
    roe = f"{_format_metric(raw.roe)}%" if raw and raw.roe is not None else _NA
    financial_health = _financial_health_label(fundamentals)
    return "\n".join(
        [
            "📑 <b>PHÂN TÍCH CƠ BẢN</b>",
            "",
            _field("P/E", pe),
            "",
            _field("P/B", pb),
            "",
            _field("EPS", eps),
            "",
            _field("ROE", roe),
            "",
            _field("Doanh thu gần nhất", _NA),
            "",
            _field("LNST gần nhất", _NA),
            "",
            _field("Sức khỏe tài chính", financial_health),
        ],
    )


def _format_ai_score_section(
    score: StockScore | None,
    analysis: StockAnalysisResult | None,
) -> str:
    technical_score = str(score.technical_score) if score else _NA
    fundamental_score = str(score.fundamental_score) if score else _NA
    news_score = str(score.news_score) if score else _NA
    total_score = str(score.overall_score) if score else _NA
    ranking = _ranking_label(score.overall_score if score else None)

    lines = [
        "🤖 <b>NHẬN ĐỊNH AI</b>",
        "",
        _field("Điểm kỹ thuật", f"{technical_score}/100"),
        "",
        _field("Điểm cơ bản", f"{fundamental_score}/100"),
        "",
        _field("Điểm tin tức", f"{news_score}/100"),
        "",
        _field("Điểm tổng", f"{total_score}/100"),
        "",
        "Xếp hạng:",
        "",
        ranking,
    ]
    if analysis and analysis.overview:
        lines.extend(["", _field("Tổng quan", escape(analysis.overview))])
    return "\n".join(lines)


def _format_price_scenario_section(
    tech: TechnicalIndicators | None,
    analysis: StockAnalysisResult | None,
) -> str:
    support = _format_vn_price(tech.support) if tech and tech.support else _NA
    resistance = _format_vn_price(tech.resistance) if tech and tech.resistance else _NA
    target_1 = _scenario_target(tech, multiplier=Decimal("1.05")) if tech else _NA
    target_2 = _scenario_target(tech, multiplier=Decimal("1.10")) if tech else _NA
    lower_target = _scenario_target(tech, multiplier=Decimal("0.95")) if tech else _NA
    range_text = f"{support} – {resistance}" if support != _NA and resistance != _NA else _NA

    positive = analysis.positive_scenario if analysis and analysis.positive_scenario else (
        f"Vượt {resistance}\n* Mục tiêu {target_1}\n* Xa hơn {target_2}"
    )
    neutral = analysis.neutral_scenario if analysis and analysis.neutral_scenario else f"Dao động {range_text}"
    negative = analysis.negative_scenario if analysis and analysis.negative_scenario else (
        f"Thủng {support}\n* Có thể giảm về {lower_target}"
    )

    return "\n".join(
        [
            "🎯 <b>KỊCH BẢN GIÁ</b>",
            "",
            "Tích cực:",
            "",
            *_scenario_lines(positive),
            "",
            "Trung lập:",
            "",
            *_scenario_lines(neutral),
            "",
            "Tiêu cực:",
            "",
            *_scenario_lines(negative),
        ],
    )


def _format_recommendation_section(
    analysis: StockAnalysisResult | None,
    score: StockScore | None,
    tech: TechnicalIndicators | None,
) -> str:
    action = _NA
    confidence = _NA
    reasons: list[str] = []

    if analysis and analysis.recommendation_action:
        action = escape(analysis.recommendation_action)
        confidence = escape(analysis.recommendation_confidence or _NA)
        reasons = _split_reasons(analysis.recommendation_reasons)
    elif tech is not None:
        action = tech.signal
        confidence = str(score.overall_score) if score else _NA

    if not reasons and analysis:
        for candidate in (analysis.positives, analysis.short_term, analysis.risks):
            if candidate and candidate.strip() and candidate.strip() not in {_NA, "Chưa có rủi ro nổi bật."}:
                reasons.append(candidate.strip())
            if len(reasons) >= 3:
                break

    while len(reasons) < 3:
        reasons.append(_NA)

    reason_lines = [f"* {escape(reason)}" for reason in reasons[:3]]
    return "\n".join(
        [
            "📌 <b>KHUYẾN NGHỊ</b>",
            "",
            action,
            "",
            _field("Độ tin cậy", f"{confidence}%"),
            "",
            "Lý do:",
            "",
            *reason_lines,
        ],
    )


def _field(label: str, value: str) -> str:
    return f"{label}:\n{value}"


def _scenario_lines(text: str) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return [_NA]
    formatted: list[str] = []
    for line in lines:
        if line.startswith("*"):
            formatted.append(escape(line))
        elif line.startswith("-"):
            formatted.append(escape(f"* {line[1:].strip()}"))
        else:
            formatted.append(f"* {escape(line)}")
    return formatted


def _split_reasons(text: str | None) -> list[str]:
    if not text:
        return []
    parts = [part.strip(" -•\t") for part in text.replace("\n", "|").split("|")]
    return [part for part in parts if part]


def _calculate_period_change(
    history: tuple[HistoricalPrice, ...],
    current_price: Decimal,
    days: int,
) -> Decimal | None:
    if not history:
        return None
    sorted_history = sorted(history, key=lambda point: point.date)
    if len(sorted_history) < 2:
        return None
    index = max(0, len(sorted_history) - days - 1)
    base_price = sorted_history[index].close
    if base_price == 0:
        return None
    return ((current_price - base_price) / base_price * Decimal("100")).quantize(Decimal("0.01"))


def _performance_comment(quote: StockQuote | None, history: tuple[HistoricalPrice, ...]) -> str:
    if quote is None:
        return _NA
    month_change = _calculate_period_change(history, quote.current_price, _PERIOD_DAYS["month"])
    if month_change is None:
        return "Theo dõi thêm diễn biến thị trường."
    if month_change >= Decimal("5"):
        return "Hiệu suất tích cực trong ngắn hạn."
    if month_change <= Decimal("-5"):
        return "Hiệu suất yếu trong ngắn hạn."
    return "Diễn biến đi ngang, cần theo dõi thêm."


def _ema_status(current_price: Decimal | None, ema: Decimal | None) -> str:
    if current_price is None or ema is None:
        return _NA
    if current_price > ema:
        return f"Giá trên EMA ({_format_vn_price(ema)})"
    if current_price < ema:
        return f"Giá dưới EMA ({_format_vn_price(ema)})"
    return f"Giá tại EMA ({_format_vn_price(ema)})"


def _rsi_status(rsi: Decimal | None) -> str:
    if rsi is None:
        return _NA
    if rsi < 30:
        return f"{rsi} — Quá bán"
    if rsi > 70:
        return f"{rsi} — Quá mua"
    return f"{rsi} — Trung tính"


def _macd_status(tech: TechnicalIndicators) -> str:
    if tech.macd is None or tech.macd_signal is None:
        return _NA
    if tech.macd_hist is not None and tech.macd_hist > 0:
        return f"MACD {tech.macd} > Signal {tech.macd_signal} — Tích cực"
    if tech.macd_hist is not None and tech.macd_hist < 0:
        return f"MACD {tech.macd} < Signal {tech.macd_signal} — Tiêu cực"
    return f"MACD {tech.macd} / Signal {tech.macd_signal} — Trung tính"


def _bollinger_status(current_price: Decimal | None, tech: TechnicalIndicators) -> str:
    if current_price is None or tech.bb_upper is None or tech.bb_lower is None:
        return _NA
    if current_price >= tech.bb_upper:
        return "Giá chạm dải trên — Có thể quá mua"
    if current_price <= tech.bb_lower:
        return "Giá chạm dải dưới — Có thể quá bán"
    return "Giá trong dải — Trung tính"


def _volume_analysis_label(liquidity: LiquidityAssessment | None) -> str:
    if liquidity is None:
        return _NA
    if liquidity.volume_ratio >= Decimal("1.5"):
        return f"Khối lượng cao hơn TB20 ({liquidity.volume_ratio}x)"
    if liquidity.volume_ratio <= Decimal("0.7"):
        return f"Khối lượng thấp hơn TB20 ({liquidity.volume_ratio}x)"
    return f"Khối lượng gần TB20 ({liquidity.volume_ratio}x)"


def _format_foreign_flow(liquidity: LiquidityAssessment) -> str:
    if liquidity.foreign_net_vol is None:
        return liquidity.foreign_flow_label
    sign = "+" if liquidity.foreign_net_vol > 0 else ""
    volume = f"{sign}{liquidity.foreign_net_vol:,}".replace(",", ".")
    return f"{liquidity.foreign_flow_label} ({volume} CP)"


def _news_impact_label(article: NewsArticle) -> str:
    text = f"{article.title} {article.summary or ''}".lower()
    positive_keywords = ("tăng", "lãi", "tích cực", "vượt", "mạnh", "growth", "profit", "upgrade")
    negative_keywords = ("giảm", "lỗ", "tiêu cực", "sụt", "yếu", "loss", "decline", "risk")
    is_positive = any(keyword in text for keyword in positive_keywords)
    is_negative = any(keyword in text for keyword in negative_keywords)
    if is_positive and not is_negative:
        return "Tích cực"
    if is_negative and not is_positive:
        return "Tiêu cực"
    return "Trung lập"


def _financial_health_label(fundamentals: dict[str, str] | None) -> str:
    if not fundamentals:
        return _NA
    ratings = list(fundamentals.values())
    if any(rating in {"Rất tốt", "Tốt"} for rating in ratings):
        if any(rating in {"Yếu"} for rating in ratings):
            return "Khá — Một số chỉ số cần theo dõi"
        return "Tốt"
    if any(rating == "Yếu" for rating in ratings):
        return "Yếu"
    return "Trung bình"


def _ranking_label(overall_score: int | None) -> str:
    if overall_score is None:
        return _NA
    for threshold, label in _RANKING_LEVELS:
        if overall_score >= threshold:
            return label
    return _RANKING_LEVELS[-1][1]


def _scenario_target(tech: TechnicalIndicators, multiplier: Decimal) -> str:
    if tech.resistance is None:
        return _NA
    return _format_vn_price((tech.resistance * multiplier).quantize(Decimal("0.01")))


def _format_metric(value: Decimal | None) -> str:
    if value is None:
        return _NA
    return _format_decimal(value)


def _format_trading_value(price: Decimal, volume: int) -> str:
    if volume <= 0:
        return _NA
    value = price * Decimal(volume)
    if value >= Decimal("1000000000000"):
        return f"{(value / Decimal('1000000000000')).quantize(Decimal('0.01'))} nghìn tỷ"
    if value >= Decimal("1000000000"):
        return f"{(value / Decimal('1000000000')).quantize(Decimal('0.01'))} tỷ"
    if value >= Decimal("1000000"):
        return f"{(value / Decimal('1000000')).quantize(Decimal('0.01'))} triệu"
    return _format_vn_price(value)


def _format_volume(volume: int) -> str:
    return f"{volume:,}".replace(",", ".")


def _format_decimal(value: Decimal) -> str:
    normalized = value.quantize(Decimal("0.01")) if value.as_tuple().exponent < -2 else value
    return f"{normalized:,}".replace(",", ".")


def _format_signed_decimal(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_format_decimal(value)}"


def _format_vn_price(value: Decimal) -> str:
    if value == value.to_integral():
        return f"{int(value):,}".replace(",", ".")
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
