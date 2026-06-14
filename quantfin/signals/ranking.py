"""Ranking engine: sort, filter, and produce top-N lists + full report."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd

from quantfin.signals.buy import BuySignalEngine
from quantfin.signals.holding import HoldingClassifier
from quantfin.valuation.market_wide import MarketSignal, MarketSnapshot
from quantfin.valuation.timing import TimingEngine, TimingSignal

logger = logging.getLogger(__name__)


class RankingEngine:
    """Rank stocks/ETFs by composite score, attach signals, build report."""

    def __init__(self, config: dict | None = None):
        self.cfg = config or {}
        self.buy_engine = BuySignalEngine()
        self.timing_engine = TimingEngine()
        self.holding_classifier = HoldingClassifier()

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def rank_stocks(
        self,
        universe: pd.DataFrame,
        pe_pct_col: str = "pe_percentile_raw",
        pb_pct_col: str = "pb_percentile_raw",
        market_signal: MarketSignal = MarketSignal.NEUTRAL,
        top_n: int = 20,
    ) -> pd.DataFrame:
        """Rank stocks by composite_score, attach buy/hold/timing signals.

        Expects universe DataFrame with columns:
        - symbol, name, composite_score, pe_dynamic, pb
        - pe_percentile_raw, pb_percentile_raw (value factor outputs)

        Returns top N rows sorted by composite_score descending, with added:
        - timing, buy_signal, holding, pe_pct, pb_pct
        """
        if "composite_score" not in universe.columns:
            logger.warning("No composite_score column; returning top by PE")
            return universe.head(top_n)

        df = universe.sort_values("composite_score", ascending=False).copy()

        # Attach timing and buy signals
        timing_signals = []
        buy_signals = []
        holdings = []

        for _, row in df.iterrows():
            score = row.get("composite_score", 50.0)
            pe_pct = row.get(pe_pct_col, 50.0)
            pb_pct = row.get(pb_pct_col, 50.0)

            timing = self.timing_engine.evaluate(market_signal, pe_pct, pb_pct)
            buy = self.buy_engine.evaluate(score, timing)
            holding = self.holding_classifier.classify(score, pe_pct, market_signal)

            timing_signals.append(timing.value)
            buy_signals.append(buy.value)
            holdings.append(holding.value)

        df["timing"] = timing_signals
        df["buy_signal"] = buy_signals
        df["holding"] = holdings
        df["pe_pct"] = df.get(pe_pct_col, 50.0)
        df["pb_pct"] = df.get(pb_pct_col, 50.0)

        # Select display columns
        display_cols = _intersect_columns(df, [
            "symbol", "name", "composite_score", "pe_dynamic", "pb",
            "pe_pct", "pb_pct", "timing", "buy_signal", "holding",
            "momentum_3m_raw", "roe_raw", "turnover_rate",
        ])
        result = df[display_cols].head(top_n).reset_index(drop=True)
        result["rank"] = range(1, len(result) + 1)
        return result

    def rank_etfs(
        self,
        universe: pd.DataFrame,
        market_signal: MarketSignal = MarketSignal.NEUTRAL,
        top_n: int = 10,
    ) -> pd.DataFrame:
        """Rank ETFs by composite_score. Simplified version (no PE valuation)."""
        if "composite_score" not in universe.columns:
            return universe.head(top_n)

        df = universe.sort_values("composite_score", ascending=False).copy()
        holdings = []
        for _, row in df.iterrows():
            score = row.get("composite_score", 50.0)
            h = self.holding_classifier.classify(score, 50.0, market_signal)
            holdings.append(h.value)
        df["holding"] = holdings

        display_cols = _intersect_columns(df, [
            "symbol", "name", "composite_score", "price", "pct_change",
            "turnover_rate", "holding",
        ])
        result = df[display_cols].head(top_n).reset_index(drop=True)
        result["rank"] = range(1, len(result) + 1)
        return result


def _intersect_columns(df: pd.DataFrame, desired: list[str]) -> list[str]:
    return [c for c in desired if c in df.columns]
