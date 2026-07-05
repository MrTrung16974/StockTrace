"""Aiogram Telegram command router."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from stocktrace.application.services.financial.financial_analysis_service import (
    FinancialAnalysisService,
)
from stocktrace.application.services.market_analysis_service import MarketAnalysisService
from stocktrace.application.services.market_data import MarketDataError, MarketDataService
from stocktrace.application.services.stock_analysis_service import StockAnalysisService
from stocktrace.application.services.watchlist import InvalidSymbolError, WatchlistService, normalize_symbol
from stocktrace.domain.ports.financial_provider import FinancialDataNotFoundError
from stocktrace.domain.value_objects.financial_period import FinancialPeriod
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.telegram.authorization import is_authorized_user, reject_unauthorized
from stocktrace.infrastructure.telegram.delivery import deliver_html_messages
from stocktrace.ai.models import AnalysisMode
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


def create_router(
    settings: Settings,
    watchlist_service: WatchlistService,
    market_data_service: MarketDataService,
    stock_analysis_service: StockAnalysisService | None = None,
    market_analysis_service: MarketAnalysisService | None = None,
    financial_analysis_service: FinancialAnalysisService | None = None,
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
        except (InvalidSymbolError, MarketDataError) as exc:
            await message.answer(str(exc))
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
                articles = await market_data_service.get_news(command.args, limit=_DEFAULT_NEWS_LIMIT)
                analysis = None
        except (InvalidSymbolError, MarketDataError) as exc:
            await message.answer(str(exc))
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
            await message.answer("Analysis service is not configured.")
            return

        thinking = await message.answer(f"⏳ Đang phân tích <b>{symbol}</b>...")
        try:
            bundle = await stock_analysis_service.analyze_symbol(
                symbol,
                mode=AnalysisMode.FULL,
                news_limit=_DEFAULT_NEWS_LIMIT,
            )
        except (InvalidSymbolError, MarketDataError) as exc:
            await thinking.edit_text(str(exc))
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
            await message.answer("Market analysis service is not configured.")
            return

        thinking = await message.answer("⏳ Đang phân tích thị trường...")
        try:
            bundle = await market_analysis_service.analyze_market(news_limit=_DEFAULT_NEWS_LIMIT)
        except Exception as exc:
            await thinking.edit_text(str(exc))
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
            await message.answer("Financial analysis service is not configured.")
            return

        args = (command.args or "").strip().split()
        if not args:
            await message.answer("Usage: /financial SYMBOL PERIOD (e.g. /financial FPT 1Y)")
            return

        try:
            symbol = normalize_symbol(args[0])
            period_str = args[1].upper() if len(args) > 1 else period_default
            period = FinancialPeriod.parse(period_str)
        except (InvalidSymbolError, ValueError) as exc:
            await message.answer(str(exc))
            return

        thinking = await message.answer(
            f"⏳ Đang phân tích tài chính <b>{symbol}</b> ({period.label})...",
        )
        try:
            dashboard = await financial_analysis_service.analyze(symbol, period)
        except FinancialDataNotFoundError as exc:
            await thinking.edit_text(str(exc))
            return
        except Exception as exc:
            logger.error("financial_analysis_failed", symbol=symbol, error=str(exc))
            await thinking.edit_text(f"Không thể phân tích tài chính cho <b>{symbol}</b>.")
            return

        try:
            await deliver_html_messages(thinking, dashboard.telegram_html)
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
            await message.answer("Financial analysis service is not configured.")
            return

        args = (command.args or "").strip().split()
        if len(args) < 2:
            await message.answer("Usage: /compare SYMBOL1 SYMBOL2 (e.g. /compare FPT CMG)")
            return

        try:
            symbol_a = normalize_symbol(args[0])
            symbol_b = normalize_symbol(args[1])
            period = FinancialPeriod.parse(args[2].upper() if len(args) > 2 else "1Y")
        except (InvalidSymbolError, ValueError) as exc:
            await message.answer(str(exc))
            return

        thinking = await message.answer(
            f"⏳ So sánh tài chính <b>{symbol_a}</b> vs <b>{symbol_b}</b>...",
        )
        try:
            result = await financial_analysis_service.compare(symbol_a, symbol_b, period)
        except FinancialDataNotFoundError as exc:
            await thinking.edit_text(str(exc))
            return

        compare_text = "\n".join([
            f"<b>Financial Comparison</b>",
            result.comparison_summary,
            "",
            f"<b>{result.symbol_a.analysis.symbol}</b>: "
            f"{result.symbol_a.analysis.score.overall_score}/10",
            f"<b>{result.symbol_b.analysis.symbol}</b>: "
            f"{result.symbol_b.analysis.score.overall_score}/10",
            "",
            f"Winner: <b>{result.winner}</b>",
        ])
        await deliver_html_messages(thinking, compare_text)

    return router
