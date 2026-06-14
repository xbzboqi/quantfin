"""Timing signal: combines market-wide + individual valuation into actionable signals."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from quantfin.valuation.market_wide import MarketSignal


class TimingSignal(str, Enum):
    STRONG_BUY = "STRONG_BUY"   # Market OVERSOLD + stock UNDERVALUED
    BUY = "BUY"                  # Market UNDERVALUED + stock UNDERVALUED
    HOLD = "HOLD"               # NEUTRAL
    REDUCE = "REDUCE"           # Market OVERVALUED or stock OVERVALUED
    SELL = "SELL"               # Market OVERBOUGHT or stock severely OVERVALUED


class TimingEngine:
    """Combine market and individual valuation into a timing signal."""

    def evaluate(
        self,
        market_signal: MarketSignal,
        stock_pe_pct: float,
        stock_pb_pct: float,
    ) -> TimingSignal:
        """Evaluate timing for a single stock given market context.

        Decision matrix:

        | Market       | Stock PE<30 & PB<30 | Stock PE>70 or PB>70 | Otherwise |
        |--------------|---------------------|-----------------------|-----------|
        | OVERSOLD     | STRONG_BUY          | HOLD                  | BUY       |
        | UNDERVALUED  | BUY                 | HOLD                  | HOLD      |
        | NEUTRAL      | BUY                 | REDUCE                | HOLD      |
        | OVERVALUED   | HOLD                | REDUCE                | REDUCE    |
        | OVERBOUGHT   | HOLD                | SELL                  | SELL      |
        """
        stock_undervalued = stock_pe_pct < 30 and stock_pb_pct < 30
        stock_overvalued = stock_pe_pct > 70 or stock_pb_pct > 70

        if market_signal == MarketSignal.OVERSOLD:
            if stock_undervalued:
                return TimingSignal.STRONG_BUY
            if stock_overvalued:
                return TimingSignal.HOLD
            return TimingSignal.BUY

        if market_signal == MarketSignal.UNDERVALUED:
            if stock_undervalued:
                return TimingSignal.BUY
            if stock_overvalued:
                return TimingSignal.HOLD
            return TimingSignal.HOLD

        if market_signal == MarketSignal.NEUTRAL:
            if stock_undervalued:
                return TimingSignal.BUY
            if stock_overvalued:
                return TimingSignal.REDUCE
            return TimingSignal.HOLD

        if market_signal == MarketSignal.OVERVALUED:
            if stock_undervalued:
                return TimingSignal.HOLD
            if stock_overvalued:
                return TimingSignal.REDUCE
            return TimingSignal.REDUCE

        # OVERBOUGHT
        if stock_undervalued:
            return TimingSignal.HOLD
        if stock_overvalued:
            return TimingSignal.SELL
        return TimingSignal.SELL
