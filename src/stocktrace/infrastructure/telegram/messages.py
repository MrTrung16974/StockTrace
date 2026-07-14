"""Telegram message builders."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from html import escape

from stocktrace.ai.models import StockAnalysisResult
from stocktrace.application.services.market_analysis_service import MarketAnalysisBundle
from stocktrace.application.services.market_data import NewsArticle, StockQuote
from stocktrace.application.services.policy_news_analysis import PolicyNewsAnalyzer
from stocktrace.application.services.stock_analysis_service import AnalysisBundle
from stocktrace.domain.entities.watchlist_item import WatchlistItem
from stocktrace.infrastructure.config import Settings

BotCommandSpec = tuple[str, str]
_MAX_DECIMAL_PLACES = -2
_MINUTES_PER_HOUR = 60
_HOURS_PER_DAY = 24
_POLICY_NEWS_ANALYZER = PolicyNewsAnalyzer()
_FINANCIAL_NEWS_SOURCES = (
    "cafef",
    "vietstock",
    "vneconomy",
    "vietnambiz",
    "vietcap",
    "ssi",
    "vnexpress",
    "reuters",
    "bloomberg",
)


def build_bot_command_specs() -> tuple[BotCommandSpec, ...]:
    """Build Telegram bot command menu specs."""
    return (
        ("status", "trạng thái hệ thống"),
        ("help", "xem danh sách lệnh"),
        ("add", "thêm mã vào danh sách theo dõi"),
        ("remove", "xóa mã khỏi danh sách theo dõi"),
        ("list", "xem danh sách theo dõi"),
        ("price", "giá mới nhất"),
        ("news", "tin tức mới nhất"),
        ("new", "tin tức đã lọc, có nguồn"),
        ("analysis", "phân tích cổ phiếu bằng AI"),
        ("market", "phân tích thị trường"),
        ("financial", "phân tích tài chính"),
        ("report", "báo cáo tài chính"),
        ("valuation", "phân tích định giá"),
        ("score", "điểm tài chính"),
        ("roe", "phân tích ROE"),
        ("debt", "phân tích nợ"),
        ("cashflow", "phân tích dòng tiền"),
        ("compare", "so sánh hai mã"),
        ("trace", "dòng thời gian theo dõi mã"),
        ("why", "giải thích nguyên nhân"),
        ("signals", "tín hiệu theo dõi"),
        ("risks", "rủi ro theo dõi"),
    )


def build_start_message() -> str:
    """Build the /start response."""
    return "\n".join(
        [
            "StockTrace đã kết nối.",
            "",
            "Lệnh:",
            "/status - trạng thái hệ thống",
            "/help - xem danh sách lệnh",
        ],
    )


def build_help_message() -> str:
    """Build the /help response."""
    return "\n".join(
        [
            "Các lệnh StockTrace:",
            "/status - trạng thái hệ thống",
            "/help - xem danh sách lệnh",
            "",
            "/add SYMBOL",
            "/remove SYMBOL",
            "/list",
            "/price SYMBOL",
            "/news SYMBOL",
            "/new SYMBOL (bí danh của /news)",
            "/analysis SYMBOL",
            "/market - phân tích thị trường",
            "",
            "Phân tích tài chính:",
            "/financial SYMBOL PERIOD (e.g. FPT 1Y)",
            "/report SYMBOL",
            "/valuation SYMBOL",
            "/score SYMBOL",
            "/roe SYMBOL",
            "/debt SYMBOL",
            "/cashflow SYMBOL",
            "/compare SYMBOL1 SYMBOL2",
            "",
            "Theo dõi diễn biến:",
            "/trace SYMBOL",
            "/why SYMBOL",
            "/signals SYMBOL",
            "/risks SYMBOL",
        ],
    )


def build_status_message(settings: Settings) -> str:
    """Build the /status response."""
    database_backend = "SQLite" if settings.database.is_sqlite else "PostgreSQL"
    return "\n".join(
        [
            "Trạng thái StockTrace",
            f"Dịch vụ: {settings.app.name}",
            f"Phiên bản: {settings.app.version}",
            f"Môi trường: {settings.environment.value}",
            f"Cơ sở dữ liệu: {database_backend}",
            f"Redis đã bật: {settings.redis.enabled}",
            f"AI đã bật: {settings.ai.enabled}",
            "Telegram: đã kết nối",
        ],
    )


def build_watchlist_message(items: Sequence[WatchlistItem]) -> str:
    """Build the /list response."""
    if not items:
        return "Danh sách theo dõi đang trống. Dùng /add MA để thêm mã."

    symbols = "\n".join(f"{index}. {item.symbol}" for index, item in enumerate(items, start=1))
    return "\n".join(["Danh sách theo dõi:", symbols])


def build_added_message(symbol: str) -> str:
    """Build the /add response."""
    return f"Đã thêm {symbol} vào danh sách theo dõi."


def build_removed_message(symbol: str, removed: bool) -> str:
    """Build the /remove response."""
    if removed:
        return f"Đã xóa {symbol} khỏi danh sách theo dõi."
    return f"{symbol} không có trong danh sách theo dõi."


def build_price_message(quote: StockQuote) -> str:
    """Build the /price response."""
    return "\n".join(
        [
            escape(quote.ticker),
            f"Giá: {_format_vn_price(quote.current_price)}",
            f"{_format_signed_decimal(quote.change_percent)}%",
        ],
    )


def build_news_message(symbol: str, articles: Sequence[NewsArticle]) -> str:
    """Build a source-aware /news response."""
    clean_symbol = escape(symbol)
    if not articles:
        return (
            f"Không có tin mới trong 7 ngày gần đây cho {clean_symbol}. "
            "Để tránh tin cũ hoặc trùng lặp, hệ thống không hiển thị các bài đó."
        )

    now = datetime.now(tz=UTC)
    lines = [
        f"📰 Tin tức đã lọc — {clean_symbol}",
        "Chỉ hiển thị tin mới, không trùng lặp. Nhãn tác động không phải khuyến nghị giao dịch.",
        "",
    ]
    for index, article in enumerate(articles, start=1):
        title = escape(article.title)
        url = escape(article.url)
        source = escape(article.source)
        lines.append(f'{index}. <a href="{url}">{title}</a>')
        lines.append(f"   Nguồn: {source} · {_published_label(article.published_at, now)}")
        policy_impact = _POLICY_NEWS_ANALYZER.analyze(article)
        if policy_impact is not None:
            lines.append(f"   🏛 {escape(policy_impact.label)} — {escape(policy_impact.reason)}")
        else:
            lines.append(f"   Độ tin cậy nguồn: {_source_quality_label(article)}")
    return "\n".join(lines)


def _published_label(published_at: datetime | None, now: datetime) -> str:
    if published_at is None:
        return "chưa xác minh thời điểm xuất bản"
    timestamp = published_at.replace(tzinfo=UTC) if published_at.tzinfo is None else published_at
    minutes = max(0, int((now - timestamp.astimezone(UTC)).total_seconds() // 60))
    if minutes < _MINUTES_PER_HOUR:
        return f"{minutes} phút trước"
    if minutes < _HOURS_PER_DAY * _MINUTES_PER_HOUR:
        return f"{minutes // _MINUTES_PER_HOUR} giờ trước"
    return f"{minutes // (_HOURS_PER_DAY * _MINUTES_PER_HOUR)} ngày trước"


def _source_quality_label(article: NewsArticle) -> str:
    source = article.source.lower()
    if any(name in source for name in _FINANCIAL_NEWS_SOURCES):
        return "nguồn tin tài chính đã nhận diện"
    return "nguồn tổng hợp — nên đối chiếu bài gốc"


def append_ai_news_section(text: str, analysis: StockAnalysisResult | None) -> str:
    """Append the AI analysis block after an existing /news message."""
    if analysis is None:
        return text
    return f"{text}\n\n{build_ai_news_section(analysis)}"


def build_ai_news_section(analysis: StockAnalysisResult) -> str:
    """Build the AI analysis section for /news."""
    return "\n".join(
        [
            "🤖 PHÂN TÍCH AI",
            "",
            f"Tổng quan:\n{escape(analysis.overview)}",
            "",
            f"Điểm tích cực:\n{escape(analysis.positives)}",
            "",
            f"Rủi ro:\n{escape(analysis.risks)}",
            "",
            f"Đánh giá ngắn hạn:\n{escape(analysis.short_term)}",
        ],
    )


def build_full_analysis_message(bundle: AnalysisBundle) -> str:
    """Build the /analysis command response."""
    from stocktrace.infrastructure.telegram.formatters import (  # noqa: PLC0415
        build_professional_analysis_report,
    )

    return build_professional_analysis_report(bundle)


def build_market_message(bundle: MarketAnalysisBundle) -> str:
    """Build the /market command response."""
    from stocktrace.infrastructure.telegram.formatters import (  # noqa: PLC0415
        build_market_analysis_report,
    )

    return build_market_analysis_report(bundle)


def build_scheduler_symbol_section(bundle: AnalysisBundle) -> str:
    """Build one symbol section for scheduled AI reports."""
    lines = [f"<b>{escape(bundle.symbol)}</b>"]
    if bundle.quote is not None:
        lines.append(f"Giá: {_format_vn_price(bundle.quote.current_price)}")
        lines.append(f"Biến động: {_format_signed_decimal(bundle.quote.change_percent)}%")

    if bundle.analysis is None:
        lines.append("Không có nhận định AI.")
        return "\n".join(lines)

    analysis = bundle.analysis
    lines.extend(
        [
            "",
            f"Tổng quan: {escape(analysis.overview)}",
            f"Điểm mạnh: {escape(analysis.positives)}",
            f"Rủi ro: {escape(analysis.risks)}",
            f"Ngắn hạn: {escape(analysis.short_term)}",
        ],
    )
    if analysis.medium_term:
        lines.append(f"Trung hạn: {escape(analysis.medium_term)}")
    if analysis.conclusion:
        lines.append(f"Kết luận: {escape(analysis.conclusion)}")
    return "\n".join(lines)


def _trend_label(change_percent: Decimal) -> str:
    if change_percent > 0:
        return "Tăng"
    if change_percent < 0:
        return "Giảm"
    return "Đi ngang"


def _format_decimal(value: Decimal) -> str:
    normalized = (
        value.quantize(Decimal("0.01"))
        if value.as_tuple().exponent < _MAX_DECIMAL_PLACES
        else value
    )
    return f"{normalized:,}"


def _format_signed_decimal(value: Decimal) -> str:
    prefix = "+" if value > 0 else ""
    return f"{prefix}{_format_decimal(value)}"


def _format_vn_price(value: Decimal) -> str:
    if value == value.to_integral():
        return f"{int(value):,}".replace(",", ".")
    formatted = f"{value:,.2f}"
    return formatted.replace(",", "_").replace(".", ",").replace("_", ".")
