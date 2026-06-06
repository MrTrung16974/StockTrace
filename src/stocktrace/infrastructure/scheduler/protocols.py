"""Scheduler protocol definitions."""

from __future__ import annotations

from typing import Protocol


class TelegramMessageBot(Protocol):
    """Minimal Telegram bot contract used by scheduled jobs."""

    async def send_message(
        self,
        chat_id: str,
        text: str,
        parse_mode: str | None = None,
        disable_web_page_preview: bool | None = None,
    ) -> object:
        """Send a Telegram message."""
        ...
