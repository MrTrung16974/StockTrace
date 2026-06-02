"""Telegram bot lifecycle runner."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.utils.token import TokenValidationError

from stocktrace.application.services.watchlist import WatchlistService
from stocktrace.infrastructure.config import Settings
from stocktrace.infrastructure.logging.config import get_logger
from stocktrace.infrastructure.telegram.handlers import create_router


class TelegramBotRunner:
    """Run Telegram polling in the application lifecycle."""

    def __init__(self, settings: Settings, watchlist_service: WatchlistService) -> None:
        self._settings = settings
        self._watchlist_service = watchlist_service
        self._logger = get_logger(__name__)
        self._bot: Bot | None = None
        self._dispatcher: Dispatcher | None = None
        self._task: asyncio.Task[None] | None = None

    @property
    def is_configured(self) -> bool:
        """Return whether the runner has enough configuration to start."""
        return (
            self._settings.telegram.bot_token is not None
            and self._settings.telegram.polling_enabled
        )

    @property
    def is_running(self) -> bool:
        """Return whether the polling task is currently running."""
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        """Start Telegram polling in the background."""
        if not self.is_configured:
            self._logger.info("telegram_polling_skipped")
            return

        token = self._settings.telegram.bot_token
        if token is None:
            return

        try:
            self._bot = Bot(
                token=token.get_secret_value(),
                default=DefaultBotProperties(parse_mode=ParseMode.HTML),
            )
        except TokenValidationError as exc:
            self._logger.error("telegram_polling_invalid_token", error=str(exc))
            self._bot = None
            return

        self._dispatcher = Dispatcher()
        self._dispatcher.include_router(create_router(self._settings, self._watchlist_service))

        self._task = asyncio.create_task(self._poll(), name="telegram-polling")
        self._logger.info("telegram_polling_started")

    async def stop(self) -> None:
        """Stop Telegram polling and close the bot session."""
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        if self._bot is not None:
            await self._bot.session.close()
            self._bot = None
        self._dispatcher = None
        self._logger.info("telegram_polling_stopped")

    async def _poll(self) -> None:
        if self._bot is None or self._dispatcher is None:
            return

        try:
            await self._bot.delete_webhook(
                drop_pending_updates=self._settings.telegram.drop_pending_updates,
            )
            await self._dispatcher.start_polling(
                self._bot,
                allowed_updates=self._dispatcher.resolve_used_update_types(),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._logger.error("telegram_polling_failed", error=str(exc))
