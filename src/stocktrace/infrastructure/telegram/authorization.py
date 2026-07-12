"""Telegram authorization helpers."""

from __future__ import annotations

from aiogram.types import Message, User

from stocktrace.infrastructure.config import TelegramSettings


def is_authorized_user(user: User | None, settings: TelegramSettings) -> bool:
    """Return whether a Telegram user is allowed to control the bot."""
    if user is None:
        return False
    if not settings.allowed_user_ids:
        return True
    return user.id in settings.allowed_user_ids


async def reject_unauthorized(message: Message) -> None:
    """Send a minimal unauthorized response."""
    await message.answer("Bạn không có quyền sử dụng bot này.")
