"""Holding period classification: short / medium / long term."""

from __future__ import annotations

from enum import Enum

from quantfin.valuation.market_wide import MarketSignal


class HoldingPeriod(str, Enum):
    SHORT = "short"     # 1-3 months
    MEDIUM = "medium"   # 3-12 months
    LONG = "long"       # 12+ months
    AVOID = "avoid"     # Not recommended


class HoldingClassifier:
    """Classify recommended holding period based on score + valuation context."""

    def classify(
        self,
        composite_score: float,
        pe_percentile: float,
        market_signal: MarketSignal,
    ) -> HoldingPeriod:
        """Determine recommended holding period.

        Logic:
        - score >= 70 + market OVERSOLD/UNDERVALUED → long
        - score >= 60 + market OVERSOLD/UNDERVALUED → medium
        - score >= 70 + market NEUTRAL → medium
        - score >= 60 + market NEUTRAL → short
        - score >= 50 + market OVERSOLD → short
        - score < 50 → avoid
        - Otherwise → short
        """
        if composite_score < 50:
            return HoldingPeriod.AVOID

        oversold_zone = market_signal in (MarketSignal.OVERSOLD, MarketSignal.UNDERVALUED)

        if composite_score >= 70 and oversold_zone:
            return HoldingPeriod.LONG
        if (composite_score >= 60 and oversold_zone) or (composite_score >= 70 and market_signal == MarketSignal.NEUTRAL):
            return HoldingPeriod.MEDIUM
        if composite_score >= 50 and market_signal == MarketSignal.OVERSOLD:
            return HoldingPeriod.SHORT

        return HoldingPeriod.SHORT
