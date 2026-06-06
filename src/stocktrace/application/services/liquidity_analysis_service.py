"""Liquidity and foreign flow analysis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from stocktrace.application.services.market_data import FundamentalData, HistoricalPrice, StockQuote


@dataclass(frozen=True, slots=True)
class LiquidityAssessment:
    """Liquidity and foreign flow assessment."""

    avg_volume_20d: int
    current_volume: int
    volume_ratio: Decimal
    foreign_buy_vol: int | None
    foreign_sell_vol: int | None
    foreign_net_vol: int | None
    status: str
    foreign_flow_label: str


class LiquidityAnalysisService:
    """Assess trading liquidity and foreign investor flow."""

    def analyze(
        self,
        quote: StockQuote | None,
        history: list[HistoricalPrice],
        fundamentals: FundamentalData,
    ) -> LiquidityAssessment:
        """Build liquidity assessment from volume and foreign flow data."""
        volumes = [point.volume for point in history if point.volume > 0]
        avg_volume = int(sum(volumes[-20:]) / len(volumes[-20:])) if volumes else 0
        current_volume = quote.volume if quote is not None else (volumes[-1] if volumes else 0)

        ratio = Decimal("0")
        if avg_volume > 0:
            ratio = (Decimal(current_volume) / Decimal(avg_volume)).quantize(Decimal("0.01"))

        if ratio >= Decimal("1.5"):
            status = "Thanh khoản cao"
        elif ratio >= Decimal("0.7"):
            status = "Thanh khoản trung bình"
        else:
            status = "Thanh khoản yếu"

        foreign_buy = fundamentals.foreign_buy_vol
        foreign_sell = fundamentals.foreign_sell_vol
        foreign_net = None
        foreign_label = "Không có dữ liệu khối ngoại"
        if foreign_buy is not None and foreign_sell is not None:
            foreign_net = foreign_buy - foreign_sell
            if foreign_net > 0:
                foreign_label = "Khối ngoại mua ròng"
            elif foreign_net < 0:
                foreign_label = "Khối ngoại bán ròng"
            else:
                foreign_label = "Khối ngoại cân bằng"

        return LiquidityAssessment(
            avg_volume_20d=avg_volume,
            current_volume=current_volume,
            volume_ratio=ratio,
            foreign_buy_vol=foreign_buy,
            foreign_sell_vol=foreign_sell,
            foreign_net_vol=foreign_net,
            status=status,
            foreign_flow_label=foreign_label,
        )
