"""Technical Analysis Service for calculating stock indicators."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from stocktrace.application.services.market_data import HistoricalPrice

@dataclass
class TechnicalIndicators:
    """Calculated technical indicators."""
    rsi: Decimal | None
    macd: Decimal | None
    macd_signal: Decimal | None
    macd_hist: Decimal | None
    ema20: Decimal | None
    ema50: Decimal | None
    ema200: Decimal | None
    bb_upper: Decimal | None
    bb_middle: Decimal | None
    bb_lower: Decimal | None
    short_term_trend: str
    mid_term_trend: str
    long_term_trend: str
    support: Decimal | None
    resistance: Decimal | None
    signal: str

class TechnicalAnalysisService:
    """Service to perform technical analysis."""

    def analyze(self, history: list[HistoricalPrice]) -> TechnicalIndicators:
        """Calculate technical indicators from historical prices."""
        if not history or len(history) < 2:
            return self._empty_indicators()

        # Sort chronologically just in case
        history = sorted(history, key=lambda x: x.date)
        closes = [float(p.close) for p in history]
        
        rsi = self._calculate_rsi(closes)
        macd, macd_signal, macd_hist = self._calculate_macd(closes)
        ema20 = self._calculate_ema(closes, 20)
        ema50 = self._calculate_ema(closes, 50)
        ema200 = self._calculate_ema(closes, 200)
        bb_upper, bb_middle, bb_lower = self._calculate_bollinger_bands(closes)

        current_price = closes[-1]
        
        # Determine trends
        short_trend = "Tăng" if ema20 and current_price > ema20 else "Giảm"
        mid_trend = "Tăng" if ema50 and current_price > ema50 else "Giảm"
        long_trend = "Tăng" if ema200 and current_price > ema200 else "Giảm"

        # Support & Resistance (Simple: 20-day min/max)
        recent_20 = closes[-20:] if len(closes) >= 20 else closes
        support = min(recent_20)
        resistance = max(recent_20)

        # Signal
        signal = "QUAN SÁT"
        if rsi and rsi < 30 and short_trend == "Tăng":
            signal = "MUA"
        elif rsi and rsi > 70 and short_trend == "Giảm":
            signal = "BÁN"
        elif short_trend == "Tăng" and mid_trend == "Tăng":
            signal = "GIỮ"

        return TechnicalIndicators(
            rsi=Decimal(str(round(rsi, 2))) if rsi is not None else None,
            macd=Decimal(str(round(macd, 2))) if macd is not None else None,
            macd_signal=Decimal(str(round(macd_signal, 2))) if macd_signal is not None else None,
            macd_hist=Decimal(str(round(macd_hist, 2))) if macd_hist is not None else None,
            ema20=Decimal(str(round(ema20, 2))) if ema20 is not None else None,
            ema50=Decimal(str(round(ema50, 2))) if ema50 is not None else None,
            ema200=Decimal(str(round(ema200, 2))) if ema200 is not None else None,
            bb_upper=Decimal(str(round(bb_upper, 2))) if bb_upper is not None else None,
            bb_middle=Decimal(str(round(bb_middle, 2))) if bb_middle is not None else None,
            bb_lower=Decimal(str(round(bb_lower, 2))) if bb_lower is not None else None,
            short_term_trend=short_trend,
            mid_term_trend=mid_trend,
            long_term_trend=long_trend,
            support=Decimal(str(round(support, 2))),
            resistance=Decimal(str(round(resistance, 2))),
            signal=signal,
        )

    def _calculate_rsi(self, prices: list[float], periods: int = 14) -> float | None:
        if len(prices) < periods + 1:
            return None
        deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[:periods]) / periods
        avg_loss = sum(losses[:periods]) / periods

        for i in range(periods, len(gains)):
            avg_gain = (avg_gain * (periods - 1) + gains[i]) / periods
            avg_loss = (avg_loss * (periods - 1) + losses[i]) / periods

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _calculate_ema(self, prices: list[float], periods: int) -> float | None:
        if len(prices) < periods:
            return None
        k = 2 / (periods + 1)
        ema = sum(prices[:periods]) / periods
        for price in prices[periods:]:
            ema = price * k + ema * (1 - k)
        return ema

    def _calculate_macd(self, prices: list[float]) -> tuple[float | None, float | None, float | None]:
        if len(prices) < 26:
            return None, None, None
        ema12 = [self._calculate_ema(prices[:i], 12) for i in range(12, len(prices) + 1)]
        ema26 = [self._calculate_ema(prices[:i], 26) for i in range(26, len(prices) + 1)]
        
        ema12_aligned = ema12[-len(ema26):]
        macd_line = [e12 - e26 for e12, e26 in zip(ema12_aligned, ema26) if e12 is not None and e26 is not None]
        
        if len(macd_line) < 9:
            return None, None, None
        
        macd_signal = self._calculate_ema(macd_line, 9)
        macd = macd_line[-1]
        if macd is not None and macd_signal is not None:
            macd_hist = macd - macd_signal
            return macd, macd_signal, macd_hist
        return None, None, None

    def _calculate_bollinger_bands(self, prices: list[float], periods: int = 20) -> tuple[float | None, float | None, float | None]:
        if len(prices) < periods:
            return None, None, None
        recent = prices[-periods:]
        sma = sum(recent) / periods
        variance = sum((x - sma) ** 2 for x in recent) / periods
        std_dev = variance ** 0.5
        return sma + (std_dev * 2), sma, sma - (std_dev * 2)

    def _empty_indicators(self) -> TechnicalIndicators:
        return TechnicalIndicators(
            rsi=None, macd=None, macd_signal=None, macd_hist=None,
            ema20=None, ema50=None, ema200=None,
            bb_upper=None, bb_middle=None, bb_lower=None,
            short_term_trend="Chưa rõ", mid_term_trend="Chưa rõ", long_term_trend="Chưa rõ",
            support=None, resistance=None, signal="QUAN SÁT"
        )
