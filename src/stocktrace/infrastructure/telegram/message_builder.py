from __future__ import annotations

from typing import List

from stocktrace.domain.entities.news_article import NewsArticle
from stocktrace.domain.entities.stock_quote import StockQuote


def build_price_message(quote: StockQuote) -> str:
    """
    Formats a StockQuote into a Telegram HTML message.

    Uses Telegram's HTML parse mode — keep tags to <b>, <i>, <a> only.
    """
    sign = "+" if quote.change >= 0 else ""
    lines = [
        f"{quote.change_emoji} <b>{quote.symbol}</b> — {quote.company_name}",
        f"",
        f"💰 Giá hiện tại:  <b>{quote.price:,.2f} {quote.currency}</b>",
        f"📊 Thay đổi:       {sign}{quote.change:,.2f} ({sign}{quote.change_percent:.2f}%)",
        f"",
        f"🔼 Cao nhất ngày:  {quote.high:,.2f}",
        f"🔽 Thấp nhất ngày: {quote.low:,.2f}",
        f"📂 Mở cửa:        {quote.open:,.2f}",
        f"⏮ Đóng cửa hôm qua: {quote.previous_close:,.2f}",
        f"📦 Khối lượng:     {quote.volume:,}",
        f"🏦 Sàn:            {quote.exchange}",
    ]

    if quote.week_52_high and quote.week_52_low:
        lines += [
            f"",
            f"📅 52 tuần: {quote.week_52_low:,.2f} – {quote.week_52_high:,.2f}",
        ]

    if quote.market_cap:
        cap = quote.market_cap
        if cap >= 1e12:
            cap_str = f"{cap/1e12:.2f}T"
        elif cap >= 1e9:
            cap_str = f"{cap/1e9:.2f}B"
        elif cap >= 1e6:
            cap_str = f"{cap/1e6:.2f}M"
        else:
            cap_str = f"{cap:,.0f}"
        lines.append(f"🏢 Vốn hóa:        {cap_str} {quote.currency}")

    lines += [f"", f"<i>Cập nhật lúc {quote.fetched_at.strftime('%H:%M:%S UTC')}</i>"]
    return "\n".join(lines)


def build_no_price_message(symbol: str) -> str:
    return (
        f"❌ Không tìm thấy dữ liệu giá cho <b>{symbol.upper()}</b>.\n\n"
        f"Kiểm tra lại mã cổ phiếu. Cổ phiếu Việt Nam cần thêm <b>.VN</b>\n"
        f"Ví dụ: <code>/price HPG.VN</code>"
    )


def build_news_message(symbol: str, articles: List[NewsArticle]) -> str:
    """
    Formats a list of NewsArticle into a Telegram HTML message.
    """
    if not articles:
        return (
            f"📭 Không tìm thấy tin tức mới cho <b>{symbol.upper()}</b>.\n\n"
            f"Thử lại sau hoặc kiểm tra mã cổ phiếu."
        )

    lines = [f"📰 <b>Tin tức mới nhất: {symbol.upper()}</b>\n"]
    for i, article in enumerate(articles, start=1):
        lines.append(
            f"{i}. <a href=\"{article.url}\">{article.title}</a>\n"
            f"   🏷 {article.source}  •  🕐 {article.age_label}\n"
        )

    lines.append(f"<i>Kéo xuống để xem thêm chi tiết tại từng đường link.</i>")
    return "\n".join(lines)


def build_no_symbol_message(command: str) -> str:
    return (
        f"⚠️ Thiếu mã cổ phiếu.\n\n"
        f"Cách dùng: <code>/{command} SYMBOL</code>\n"
        f"Ví dụ: <code>/{command} AAPL</code> hoặc <code>/{command} HPG.VN</code>"
    )
