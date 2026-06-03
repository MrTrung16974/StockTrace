from __future__ import annotations

import logging
from typing import List

from telegram import Update
from telegram.ext import BaseHandler, ContextTypes

logger = logging.getLogger(__name__)


class AuthorizationMiddleware:
    """
    Inbound adapter middleware: rejects Telegram updates from unknown users.

    When allowed_user_ids is empty, ALL users are allowed (open mode).
    When populated, only listed user IDs may interact with the bot.
    """

    def __init__(self, allowed_user_ids: List[int]) -> None:
        self._allowed = set(allowed_user_ids)

    def is_allowed(self, update: Update) -> bool:
        if not self._allowed:
            return True
        user = update.effective_user
        if user is None:
            return False
        return user.id in self._allowed

    async def check(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
        """
        Returns True if the user is authorized.
        Sends an unauthorized message and returns False otherwise.
        """
        if self.is_allowed(update):
            return True

        user = update.effective_user
        user_id = user.id if user else "unknown"
        logger.warning("Unauthorized Telegram access attempt from user_id=%s", user_id)
        if update.effective_message:
            await update.effective_message.reply_text(
                "⛔ Bạn không có quyền sử dụng bot này."
            )
        return False
