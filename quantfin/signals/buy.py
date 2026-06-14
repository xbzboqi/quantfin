"""Buy signal: combines factor score + timing into actionable buy signals."""

from __future__ import annotations

from enum import Enum

from quantfin.valuation.timing import TimingSignal


class BuySignal(str, Enum):
    STRONG_BUY = "STRONG_BUY"   # High score + ideal timing
    BUY = "BUY"                  # Good score + favorable timing
    WATCH = "WATCH"              # Decent score, wait for better timing
    NO_SIGNAL = "NO_SIGNAL"     # No buy signal


class BuySignalEngine:
    """Generate buy signals from factor score + valuation timing."""

    def evaluate(
        self,
        composite_score: float,
        timing: TimingSignal,
    ) -> BuySignal:
        """Evaluate buy signal.

        Logic:
        - score >= 70 AND timing in (STRONG_BUY, BUY) => STRONG_BUY
        - score >= 60 AND timing in (STRONG_BUY, BUY, HOLD) => BUY
        - score >= 50 AND timing == STRONG_BUY => BUY
        - score >= 50 => WATCH
        - All other => NO_SIGNAL
        """
        # Never buy when timing says reduce or sell
        if timing in (TimingSignal.SELL, TimingSignal.REDUCE):
            return BuySignal.NO_SIGNAL

        if composite_score >= 70 and timing in (TimingSignal.STRONG_BUY, TimingSignal.BUY):
            return BuySignal.STRONG_BUY
        if composite_score >= 60 and timing in (TimingSignal.STRONG_BUY, TimingSignal.BUY, TimingSignal.HOLD):
            return BuySignal.BUY
        if composite_score >= 50 and timing == TimingSignal.STRONG_BUY:
            return BuySignal.BUY
        if composite_score >= 50:
            return BuySignal.WATCH
        return BuySignal.NO_SIGNAL
