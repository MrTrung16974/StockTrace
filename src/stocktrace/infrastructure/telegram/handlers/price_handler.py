from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from stocktrace.application.queries.stock_queries import GetPriceQuery
from stocktrace.application.services.stock_query_service import StockQueryService
from stocktrace.infrastructure.telegram.message_builder import (
    build_no_price_message,
    build_no_symbol_message,
    build_price_message,
)
from stocktrace.infrastructure.telegram.middleware.auth import AuthorizationMiddleware

logger = logging.getLogger(__name__)


class PriceHandler:
    """
    Inbound adapter: handles the /price SYMBOL Telegram command.

    Flow:
        /price HPG.VN
            -> auth check
            -> GetPriceQuery(symbol="HPG.VN")
            -> StockQueryService.get_price()
            -> YahooFinanceProvider.get_quote()
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

        # Parse symbol from command args
        args = context.args or []
        if not args:
            await update.effective_message.reply_text(
                build_no_symbol_message("price"),
                parse_mode=ParseMode.HTML,
            )
            return

        symbol = args[0].upper().strip()
        logger.info("PriceHandler: user=%s symbol=%s", update.effective_user.id, symbol)

        # Send "loading" indicator while fetching
        thinking = await update.effective_message.reply_text(
            f"⏳ Đang lấy giá <b>{symbol}</b>...",
            parse_mode=ParseMode.HTML,
        )

        query = GetPriceQuery(symbol=symbol)
        quote = await self._service.get_price(query)

        if quote is None:
            text = build_no_price_message(symbol)
        else:
            text = build_price_message(quote)

        # Edit the "loading" message with the real result
        await thinking.edit_text(text, parse_mode=ParseMode.HTML)
