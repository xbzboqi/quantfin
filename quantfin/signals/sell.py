"""Sell / stop-profit signals: target return, overvaluation, momentum decay."""

from __future__ import annotations

from enum import Enum
from typing import Optional


class SellSignal(str, Enum):
    TAKE_PROFIT = "TAKE_PROFIT"   # Target return reached
    SELL = "SELL"                  # Overvaluation + momentum exhaustion
    REDUCE = "REDUCE"              # Getting expensive
    WEAKENING = "WEAKENING"        # Score declining, watch closely
    HOLD = "HOLD"                  # No sell signal


class SellSignalEngine:
    """Generate stop-profit / exit signals."""

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self.stop_cfg = cfg.get("stop_profit", {})

    def evaluate(
        self,
        position_return: float,         # e.g., 0.12 = 12% gain
        days_held: int,
        current_score: float,
        entry_score: Optional[float],
        pe_percentile: float,
        mid_term_momentum: float,       # 20-day return, e.g., -0.02 = -2%
    ) -> SellSignal:
        """Evaluate sell/exit signals based on multiple criteria.

        Priority:
        1. Target return reached → TAKE_PROFIT
        2. Extreme overvaluation → SELL
        3. Score decline + negative momentum → SELL
        4. Moderate overvaluation → REDUCE
        5. Score weakening → WEAKENING
        """
        # 1. Target return
        target = self._target_return(days_held)
        if position_return >= target:
            return SellSignal.TAKE_PROFIT

        # 2. Overvaluation
        if pe_percentile > 95:
            return SellSignal.SELL
        if pe_percentile > 85:
            return SellSignal.REDUCE

        # 3. Score decline (only if we have entry score)
        if entry_score is not None and entry_score > 0:
            decline = (entry_score - current_score) / entry_score
            if decline >= self.stop_cfg.get("score_decline_exit", 0.50):
                if mid_term_momentum < -0.05:
                    return SellSignal.SELL
                return SellSignal.WEAKENING
            if decline >= self.stop_cfg.get("score_decline_warning", 0.30):
                return SellSignal.WEAKENING

        return SellSignal.HOLD

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _target_return(self, days_held: int) -> float:
        """Get target return based on holding period."""
        if days_held <= 90:
            return self.stop_cfg.get("short_term_return_target", 0.08)
        if days_held <= 365:
            return self.stop_cfg.get("medium_term_return_target", 0.15)
        return self.stop_cfg.get("long_term_return_target", 0.25)
