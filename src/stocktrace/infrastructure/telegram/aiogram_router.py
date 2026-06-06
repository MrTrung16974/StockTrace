"""Aiogram Telegram command router."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from stocktrace.application.services.market_data import MarketDataError, MarketDataService
from stocktrace.application.services.stock_analysis_service import StockAnalysisService
from stocktrace.application.services.watchlist import InvalidSymbolError, WatchlistService, normalize_symbol
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.telegram.authorization import is_authorized_user, reject_unauthorized
from stocktrace.ai.models import AnalysisMode
from stocktrace.infrastructure.telegram.messages import (
    append_ai_news_section,
    build_added_message,
    build_full_analysis_message,
    build_help_message,
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
) -> Router:
    """Create the Telegram command router."""
    router = Router(name="stocktrace-telegram")

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

        await thinking.edit_text(build_full_analysis_message(bundle))

    return router
