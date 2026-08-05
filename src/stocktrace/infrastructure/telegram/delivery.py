"""Telegram message delivery helpers."""

from __future__ import annotations

import re

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def split_telegram_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a message into Telegram-safe chunks without losing any content."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    remaining = text
    while len(remaining) > limit:
        # Prefer a line boundary, then a word boundary.  Fall back to a hard
        # split so an unusually long AI-generated line cannot exceed Telegram's
        # message limit indefinitely.
        boundary = remaining.rfind("\n", 0, limit + 1)
        if boundary <= 0:
            boundary = remaining.rfind(" ", 0, limit + 1)
        if boundary <= 0:
            boundary = limit
        elif remaining[boundary] == "\n":
            boundary += 1

        parts.append(remaining[:boundary])
        remaining = remaining[boundary:]

    if remaining:
        parts.append(remaining)
    return parts


def strip_html_tags(text: str) -> str:
    """Convert a Telegram HTML message to plain text."""
    without_links = re.sub(r'<a href="[^"]*">([^<]*)</a>', r"\1", text)
    return re.sub(r"</?[^>]+>", "", without_links)


async def deliver_html_messages(anchor: Message, text: str) -> None:
    """Edit the anchor message and send any overflow as follow-up messages."""
    parts = split_telegram_message(text)
    html_kwargs = {
        "parse_mode": ParseMode.HTML,
        "disable_web_page_preview": True,
    }

    await _send_part(anchor.edit_text, parts[0], html_kwargs=html_kwargs)
    for part in parts[1:]:
        await _send_part(anchor.answer, part, html_kwargs=html_kwargs)


async def _send_part(
    send_callable,
    text: str,
    *,
    html_kwargs: dict,
) -> None:
    try:
        await send_callable(text, **html_kwargs)
    except TelegramBadRequest:
        await send_callable(strip_html_tags(text))
