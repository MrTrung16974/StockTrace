"""Telegram command handlers.

The active Telegram adapter is aiogram. This package remains as a compatibility
import path for older code that imported ``stocktrace.infrastructure.telegram.handlers``.
"""

from __future__ import annotations

from stocktrace.infrastructure.telegram.aiogram_router import create_router

__all__ = ["create_router"]
