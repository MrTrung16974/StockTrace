"""Telegram message delivery helpers."""

from __future__ import annotations

import re

from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message

TELEGRAM_MAX_MESSAGE_LENGTH = 4096


def split_telegram_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into Telegram-safe chunks."""
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.split("\n"):
        extra = len(line) + (1 if current else 0)
        if current and current_len + extra > limit:
            parts.append("\n".join(current))
            current = [line]
            current_len = len(line)
            continue
        if current:
            current_len += extra
        else:
            current_len = len(line)
        current.append(line)

    if current:
        parts.append("\n".join(current))
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
