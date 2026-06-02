"""Telegram command handlers."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandObject
from aiogram.types import Message

from stocktrace.application.services.watchlist import InvalidSymbolError, WatchlistService
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.telegram.authorization import is_authorized_user, reject_unauthorized
from stocktrace.infrastructure.telegram.messages import (
    build_added_message,
    build_help_message,
    build_removed_message,
    build_start_message,
    build_status_message,
    build_watchlist_message,
)


def create_router(settings: Settings, watchlist_service: WatchlistService) -> Router:
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

    return router
