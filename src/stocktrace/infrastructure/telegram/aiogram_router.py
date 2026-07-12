"""Aiogram Telegram command router."""

from __future__ import annotations

from decimal import Decimal
from html import escape

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from stocktrace.ai.models import AnalysisMode
from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.application.services.market_analysis_service import MarketAnalysisService
from stocktrace.application.services.market_data import MarketDataError, MarketDataService
from stocktrace.application.services.stock_analysis_service import StockAnalysisService
from stocktrace.application.services.trace import TraceService
from stocktrace.application.services.watchlist import (
    InvalidSymbolError,
    WatchlistService,
    normalize_symbol,
)
from stocktrace.domain.entities.financial import FinancialDashboard, FinancialRatio
from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.telegram.authorization import is_authorized_user, reject_unauthorized
from stocktrace.infrastructure.telegram.delivery import deliver_html_messages
from stocktrace.infrastructure.telegram.messages import (
    append_ai_news_section,
    build_added_message,
    build_full_analysis_message,
    build_help_message,
    build_market_message,
    build_news_message,
    build_price_message,
    build_removed_message,
    build_start_message,
    build_status_message,
    build_watchlist_message,
)

_DEFAULT_NEWS_LIMIT = 5
_COMPARE_SYMBOL_COUNT = 2
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
_CATEGORY_VI = {
    "Growth": "Tăng trưởng",
    "Profitability": "Sinh lời",
    "Debt": "Nợ",
    "Cash Flow": "Dòng tiền",
    "Valuation": "Định giá",
}


def _financial_usage(command_name: str) -> str:
    """Return command-specific usage text."""
    usages = {
        "financial": "Cách dùng: /financial MÃ KỲ (vd: /financial HPG 1Y)",
        "finacial": "Cách dùng: /financial MÃ KỲ (vd: /financial HPG 1Y)",
        "report": "Cách dùng: /report MÃ (vd: /report HPG)",
        "valuation": "Cách dùng: /valuation MÃ (vd: /valuation HPG)",
        "score": "Cách dùng: /score MÃ (vd: /score HPG)",
        "roe": "Cách dùng: /roe MÃ (vd: /roe HPG)",
        "debt": "Cách dùng: /debt MÃ (vd: /debt HPG)",
        "cashflow": "Cách dùng: /cashflow MÃ (vd: /cashflow HPG)",
    }
    return usages.get(command_name, usages["financial"])


def _format_decimal(value: Decimal | None, suffix: str = "", digits: int = 2) -> str:
    """Format a Decimal value for Telegram output."""
    if value is None:
        return "Chưa có"
    return f"{value:,.{digits}f}{suffix}"


def _format_money(value: Decimal | None) -> str:
    """Format VND values compactly."""
    if value is None:
        return "Chưa có"
    if abs(value) >= Decimal("1000000000000"):
        return f"{value / Decimal('1000000000000'):,.2f} nghìn tỷ đồng"
    if abs(value) >= Decimal("1000000000"):
        return f"{value / Decimal('1000000000'):,.0f} tỷ đồng"
    return f"{value:,.0f} đồng"


def _recommendation_vi(value: str) -> str:
    return _RECOMMENDATION_VI.get(value, value)


def _valuation_status_vi(value: str) -> str:
    return _VALUATION_STATUS_VI.get(value, value)


def _category_vi(value: str) -> str:
    return _CATEGORY_VI.get(value, value)


def _latest_ratio(dashboard: FinancialDashboard) -> FinancialRatio | None:
    """Return the latest ratio snapshot from a dashboard."""
    ratios = dashboard.analysis.ratios
    return ratios[-1] if ratios else None


def _build_financial_command_response(
    dashboard: FinancialDashboard,
    command_name: str,
) -> str:
    """Build command-specific Telegram output for financial commands."""
    analysis = dashboard.analysis
    symbol = escape(analysis.symbol)
    company = escape(analysis.company_name)
    latest = _latest_ratio(dashboard)
    score = analysis.score
    quality = analysis.quality
    valuation = analysis.valuation
    recommendation = _recommendation_vi(score.recommendation.value)
    valuation_status = _valuation_status_vi(valuation.status.value)

    if command_name in {"financial", "finacial", "report"}:
        return dashboard.telegram_html

    lines: list[str]
    if command_name == "valuation":
        lines = [
            f"<b>Định giá {symbol}</b>",
            company,
            f"Trạng thái: <b>{valuation_status}</b>",
            f"Giá hiện tại: {_format_money(valuation.current_price)}",
            f"Giá mục tiêu: {_format_money(valuation.target_price)}",
            f"PE hiện tại: {_format_decimal(valuation.current_pe, digits=1)}",
            f"PE trung bình: {_format_decimal(valuation.average_pe, digits=1)}",
            f"PB hiện tại: {_format_decimal(valuation.current_pb, digits=1)}",
            f"PB trung bình: {_format_decimal(valuation.average_pb, digits=1)}",
            "Lưu ý: P/E/P/B lịch sử và giá mục tiêu chỉ hiển thị khi có "
            "giá lịch sử đã xác minh.",
        ]
    elif command_name == "score":
        lines = [
            f"<b>Điểm tài chính {symbol}</b>",
            company,
            f"Điểm tổng hợp: <b>{score.overall_score}/10</b>",
            f"Tín hiệu định lượng: <b>{recommendation}</b>",
            f"Chất lượng dữ liệu: <b>{quality.score:.0f}/100</b>",
            "",
            "Nhóm điểm:",
        ]
        lines.extend(
            f"- {_category_vi(item.category)}: "
            f"{_format_decimal(item.score / Decimal('10'), digits=1)}/10"
            for item in score.categories
        )
        if quality.issues:
            lines.append("")
            lines.append("Chưa đủ điều kiện phát tín hiệu đầu tư:")
            lines.extend(f"- {issue}" for issue in quality.issues)
    elif command_name == "roe":
        lines = [
            f"<b>ROE {symbol}</b>",
            company,
            f"ROE: {_format_decimal(latest.roe if latest else None, '%')}",
            f"ROA: {_format_decimal(latest.roa if latest else None, '%')}",
            f"Biên lợi nhuận ròng: {_format_decimal(latest.net_margin if latest else None, '%')}",
            f"Điểm sinh lời: {_format_decimal(score.profitability_score, digits=1)}/10",
        ]
    elif command_name == "debt":
        lines = [
            f"<b>Nợ {symbol}</b>",
            company,
            f"Nợ/Vốn chủ sở hữu: {_format_decimal(latest.debt_to_equity if latest else None)}",
            f"Nợ/Tài sản: {_format_decimal(latest.debt_to_asset if latest else None)}",
            f"Thanh toán hiện hành: {_format_decimal(latest.current_ratio if latest else None)}",
            f"Thanh toán nhanh: {_format_decimal(latest.quick_ratio if latest else None)}",
            f"Điểm nợ: {_format_decimal(score.debt_score, digits=1)}/10",
        ]
    elif command_name == "cashflow":
        operating_cf = latest.operating_cash_flow if latest else None
        free_cf = latest.free_cash_flow if latest else None
        lines = [
            f"<b>Dòng tiền {symbol}</b>",
            company,
            f"Dòng tiền HĐKD: {_format_money(operating_cf)}",
            f"Dòng tiền tự do: {_format_money(free_cf)}",
            f"Tăng trưởng FCF: {_format_decimal(latest.fcf_growth if latest else None, '%')}",
            f"Chuyển đổi tiền mặt: {_format_decimal(latest.cash_conversion if latest else None)}",
            f"Điểm dòng tiền: {_format_decimal(score.cash_flow_score, digits=1)}/10",
        ]
    else:
        lines = [dashboard.telegram_html]

    return "\n".join(lines)


def create_router(  # noqa: PLR0915
    settings: Settings,
    watchlist_service: WatchlistService,
    market_data_service: MarketDataService,
    stock_analysis_service: StockAnalysisService | None = None,
    market_analysis_service: MarketAnalysisService | None = None,
    financial_analysis_service: FinancialAnalysisService | None = None,
    trace_service: TraceService | None = None,
) -> Router:
    """Create the Telegram command router."""
    router = Router(name="stocktrace-telegram")
    logger = get_logger(__name__)

    @router.message(Command("start"))
    async def start(message: Message) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await message.answer(build_start_message())

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await message.answer(build_help_message())

    @router.message(Command("status"))
    async def status(message: Message) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await message.answer(build_status_message(settings))

    @router.message(Command("add"))
    async def add(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        if message.from_user is None:
            await reject_unauthorized(message)
            return

        try:
            item = await watchlist_service.add_symbol(
                owner_id=str(message.from_user.id),
                raw_symbol=command.args,
            )
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return

        await message.answer(build_added_message(item.symbol))

    @router.message(Command("remove"))
    async def remove(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        if message.from_user is None:
            await reject_unauthorized(message)
            return

        try:
            removed = await watchlist_service.remove_symbol(
                owner_id=str(message.from_user.id),
                raw_symbol=command.args,
            )
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return

        symbol = command.args.strip().upper() if command.args else ""
        await message.answer(build_removed_message(symbol=symbol, removed=removed))

    @router.message(Command("list"))
    async def list_symbols(message: Message) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        if message.from_user is None:
            await reject_unauthorized(message)
            return

        items = await watchlist_service.list_symbols(owner_id=str(message.from_user.id))
        await message.answer(build_watchlist_message(items))

    @router.message(Command("price"))
    async def price(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return

        try:
            quote = await market_data_service.get_quote(command.args)
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return
        except MarketDataError:
            await message.answer("Không thể lấy dữ liệu giá. Vui lòng thử lại sau.")
            return

        await message.answer(build_price_message(quote))

    @router.message(Command("news"))
    async def news(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return

        try:
            symbol = normalize_symbol(command.args)
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return

        try:
            if stock_analysis_service is not None and stock_analysis_service.is_enabled:
                articles, analysis = await stock_analysis_service.fetch_and_analyze_news(
                    symbol,
                    limit=_DEFAULT_NEWS_LIMIT,
                )
            else:
                articles = await market_data_service.get_news(
                    command.args,
                    limit=_DEFAULT_NEWS_LIMIT,
                )
                analysis = None
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return
        except MarketDataError:
            await message.answer("Không thể lấy tin tức. Vui lòng thử lại sau.")
            return

        response = build_news_message(symbol=symbol, articles=articles)
        if analysis is not None:
            response = append_ai_news_section(response, analysis)
        await message.answer(response)

    @router.message(Command("analysis"))
    async def analysis(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return

        try:
            symbol = normalize_symbol(command.args)
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return

        if stock_analysis_service is None:
            await message.answer("Dịch vụ phân tích chưa được cấu hình.")
            return

        thinking = await message.answer(f"⏳ Đang phân tích <b>{symbol}</b>...")
        try:
            bundle = await stock_analysis_service.analyze_symbol(
                symbol,
                mode=AnalysisMode.FULL,
                news_limit=_DEFAULT_NEWS_LIMIT,
            )
        except InvalidSymbolError as exc:
            await thinking.edit_text(str(exc))
            return
        except MarketDataError:
            await thinking.edit_text(
                "Không thể phân tích dữ liệu thị trường. Vui lòng thử lại sau.",
            )
            return

        try:
            report = build_full_analysis_message(bundle)
            await deliver_html_messages(thinking, report)
        except Exception as exc:
            logger.error("analysis_delivery_failed", symbol=symbol, error=str(exc))
            await thinking.edit_text(
                f"Không thể gửi báo cáo phân tích cho <b>{symbol}</b>. Vui lòng thử lại sau.",
            )

    @router.message(Command("market", "market_analysis"))
    async def market_analysis(message: Message) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return

        if market_analysis_service is None:
            await message.answer("Dịch vụ phân tích thị trường chưa được cấu hình.")
            return

        thinking = await message.answer("⏳ Đang phân tích thị trường...")
        try:
            bundle = await market_analysis_service.analyze_market(news_limit=_DEFAULT_NEWS_LIMIT)
        except Exception as exc:
            logger.error("market_analysis_failed", error=str(exc))
            await thinking.edit_text("Không thể phân tích thị trường. Vui lòng thử lại sau.")
            return

        try:
            report = build_market_message(bundle)
            await deliver_html_messages(thinking, report)
        except Exception as exc:
            logger.error("market_analysis_delivery_failed", error=str(exc))
            await thinking.edit_text(
                "Không thể gửi báo cáo phân tích thị trường. Vui lòng thử lại sau.",
            )

    async def _run_financial_command(
        message: Message,
        command: CommandObject,
        period_default: str = "1Y",
    ) -> None:
        """Shared handler for financial analysis commands."""
        if financial_analysis_service is None:
            await message.answer("Dịch vụ phân tích tài chính chưa được cấu hình.")
            return

        command_name = (getattr(command, "command", "") or "financial").lower()
        args = (command.args or "").strip().split()
        if not args:
            await message.answer(_financial_usage(command_name))
            return

        try:
            symbol = normalize_symbol(args[0])
            period_str = args[1].upper() if len(args) > 1 else period_default
            period = FinancialPeriod.parse(period_str)
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return
        except ValueError:
            await message.answer("Kỳ phân tích không hợp lệ. Vui lòng dùng 1M, 3M, 6M, 1Y hoặc 3Y.")
            return

        thinking = await message.answer(
            f"⏳ Đang phân tích tài chính <b>{symbol}</b> ({period.label})...",
        )
        try:
            dashboard = await financial_analysis_service.analyze(symbol, period)
        except FinancialDataNotFoundError:
            await thinking.edit_text(
                "\n".join(
                    [
                        f"Không tìm thấy dữ liệu báo cáo tài chính cho <b>{symbol}</b>.",
                        "Vui lòng thử mã khác hoặc đồng bộ nhà cung cấp dữ liệu "
                        "tài chính chính thức.",
                    ],
                ),
            )
            return
        except Exception as exc:
            logger.error("financial_analysis_failed", symbol=symbol, error=str(exc))
            await thinking.edit_text(f"Không thể phân tích tài chính cho <b>{symbol}</b>.")
            return

        try:
            await deliver_html_messages(
                thinking,
                _build_financial_command_response(dashboard, command_name),
            )
        except Exception as exc:
            logger.error("financial_delivery_failed", symbol=symbol, error=str(exc))
            await thinking.edit_text(f"Không thể gửi báo cáo tài chính cho <b>{symbol}</b>.")

    @router.message(Command("financial"))
    async def financial(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await _run_financial_command(message, command)

    @router.message(Command("report"))
    async def report(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await _run_financial_command(message, command, period_default="1Y")

    @router.message(Command("valuation"))
    async def valuation(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await _run_financial_command(message, command, period_default="1Y")

    @router.message(Command("score"))
    async def score(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await _run_financial_command(message, command, period_default="1Y")

    @router.message(Command("roe", "debt", "cashflow"))
    async def financial_metric(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await _run_financial_command(message, command, period_default="1Y")

    @router.message(Command("compare"))
    async def compare(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return

        if financial_analysis_service is None:
            await message.answer("Dịch vụ phân tích tài chính chưa được cấu hình.")
            return

        args = (command.args or "").strip().split()
        if len(args) < _COMPARE_SYMBOL_COUNT:
            await message.answer("Cách dùng: /compare MA1 MA2 (vd: /compare FPT CMG)")
            return

        try:
            symbol_a = normalize_symbol(args[0])
            symbol_b = normalize_symbol(args[1])
            period = FinancialPeriod.parse(
                args[_COMPARE_SYMBOL_COUNT].upper() if len(args) > _COMPARE_SYMBOL_COUNT else "1Y",
            )
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return
        except ValueError:
            await message.answer("Kỳ phân tích không hợp lệ. Vui lòng dùng 1M, 3M, 6M, 1Y hoặc 3Y.")
            return

        thinking = await message.answer(
            f"⏳ So sánh tài chính <b>{symbol_a}</b> vs <b>{symbol_b}</b>...",
        )
        try:
            result = await financial_analysis_service.compare(symbol_a, symbol_b, period)
        except FinancialDataNotFoundError:
            await thinking.edit_text(
                "Không tìm thấy dữ liệu tài chính cho hai mã đã chọn. Vui lòng thử mã khác.",
            )
            return

        compare_text = "\n".join(
            [
                "<b>So sánh tài chính</b>",
                result.comparison_summary,
                "",
                f"<b>{result.symbol_a.analysis.symbol}</b>: "
                f"{result.symbol_a.analysis.score.overall_score}/10",
                f"<b>{result.symbol_b.analysis.symbol}</b>: "
                f"{result.symbol_b.analysis.score.overall_score}/10",
                "",
                f"Mã có điểm cao hơn: <b>{result.winner}</b>",
            ]
        )
        await deliver_html_messages(thinking, compare_text)

    async def _run_trace_command(message: Message, command: CommandObject) -> None:
        if trace_service is None:
            await message.answer("Dịch vụ theo dõi diễn biến chưa được cấu hình.")
            return

        try:
            symbol = normalize_symbol(command.args)
        except InvalidSymbolError as exc:
            await message.answer(str(exc))
            return

        command_name = getattr(command, "command", "") or ""
        thinking = await message.answer(f"⏳ Đang theo dõi diễn biến <b>{symbol}</b>...")
        try:
            if command_name == "why":
                explanation = await trace_service.explain(symbol, limit=10)
                lines = [
                    f"<b>Giải thích {explanation.symbol}</b>",
                    explanation.summary,
                    "",
                    "<b>Nguyên nhân</b>",
                    *(f"- {reason}" for reason in explanation.reasons),
                    "",
                    "<b>Rủi ro</b>",
                    *(f"- {risk}" for risk in explanation.risks),
                    "",
                    "<b>Theo dõi tiếp</b>",
                    *(f"- {item}" for item in explanation.next_watch),
                ]
                await deliver_html_messages(thinking, "\n".join(lines))
                return

            timeline = await trace_service.build_timeline(symbol, limit=10)
        except Exception as exc:
            logger.error("trace_timeline_failed", symbol=symbol, error=str(exc))
            await thinking.edit_text(f"Không thể theo dõi diễn biến của <b>{symbol}</b>.")
            return

        score = timeline.score
        lines = [
            f"<b>Theo dõi diễn biến {timeline.symbol}</b>",
            f"Tín hiệu: {score.signal_score}/100",
            f"Rủi ro: {score.risk_score}/100",
            f"Độ tin cậy: {score.conviction_score}/100",
            f"Sự kiện: {score.event_count}",
        ]

        if not timeline.events:
            lines.append("")
            lines.append("Chưa có sự kiện theo dõi chính thống cho mã này.")
        else:
            lines.append("")
            lines.append("<b>Sự kiện mới nhất</b>")
            for event in timeline.events[:5]:
                lines.append(
                    f"- [{event.severity.value}] {event.title} " f"({event.source.code})",
                )

        await deliver_html_messages(thinking, "\n".join(lines))

    @router.message(Command("trace", "why", "signals", "risks"))
    async def trace(message: Message, command: CommandObject) -> None:
        if not is_authorized_user(message.from_user, settings.telegram):
            await reject_unauthorized(message)
            return
        await _run_trace_command(message, command)

    return router
