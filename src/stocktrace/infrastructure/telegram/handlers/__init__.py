"""Telegram command handler registration."""

from __future__ import annotations

from telegram.ext import Application, CommandHandler

from stocktrace.bootstrap.container import Container


def register_handlers(app: Application, container: Container) -> None:
    """Register all Telegram command handlers onto the Application."""
    app.add_handler(CommandHandler("price", container.price_handler.handle))
    app.add_handler(CommandHandler("news", container.news_handler.handle))


__all__ = ["register_handlers"]
