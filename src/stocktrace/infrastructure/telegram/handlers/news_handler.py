from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from stocktrace.application.queries.stock_queries import GetNewsQuery
from stocktrace.application.services.stock_query_service import StockQueryService
from stocktrace.infrastructure.telegram.message_builder import (
    build_news_message,
    build_no_symbol_message,
)
from stocktrace.infrastructure.telegram.middleware.auth import AuthorizationMiddleware

logger = logging.getLogger(__name__)

_DEFAULT_NEWS_LIMIT = 5


class NewsHandler:
    """
    Inbound adapter: handles the /news SYMBOL Telegram command.

    Flow:
        /news HPG.VN
            -> auth check
            -> GetNewsQuery(symbol="HPG.VN", limit=5)
            -> StockQueryService.get_news()
            -> YahooNewsProvider.get_news()   [+ Google News fallback]
            -> format & reply
    """

    def __init__(
        self,
        service: StockQueryService,
        auth: AuthorizationMiddleware,
    ) -> None:
        self._service = service
        self._auth = auth

    async def handle(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._auth.check(update, context):
            return

        if not update.effective_message:
            return

        args = context.args or []
        if not args:
            await update.effective_message.reply_text(
                build_no_symbol_message("news"),
                parse_mode=ParseMode.HTML,
            )
            return

        symbol = args[0].upper().strip()
        logger.info("NewsHandler: user=%s symbol=%s", update.effective_user.id, symbol)

        thinking = await update.effective_message.reply_text(
            f"⏳ Đang tìm tin tức cho <b>{symbol}</b>...",
            parse_mode=ParseMode.HTML,
        )

        query = GetNewsQuery(symbol=symbol, limit=_DEFAULT_NEWS_LIMIT)
        articles = await self._service.get_news(query)

        text = build_news_message(symbol, articles)
        await thinking.edit_text(
            text,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
