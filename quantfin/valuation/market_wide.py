"""Market-wide valuation indicators: PE/PB percentile, yield spread."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum

import pandas as pd

from quantfin.data.cache import DataCache
from quantfin.data.fetcher import fetch_market_pe_ttm, fetch_market_pb, fetch_bond_yield_10y

logger = logging.getLogger(__name__)


class MarketSignal(str, Enum):
    OVERSOLD = "OVERSOLD"          # PE & PB both low → strong buy zone
    UNDERVALUED = "UNDERVALUED"    # PE or PB low → buy zone
    NEUTRAL = "NEUTRAL"            # Both in middle range
    OVERVALUED = "OVERVALUED"      # PE or PB high → caution
    OVERBOUGHT = "OVERBOUGHT"      # PE & PB both high → sell zone


@dataclass
class MarketSnapshot:
    """Snapshot of market-wide valuation at a point in time."""
    pe_median: float = 0.0
    pe_percentile: float = 50.0
    pb_median: float = 0.0
    pb_percentile: float = 50.0
    bond_yield_10y: float = 0.0
    yield_spread: float = 0.0          # (1/PE) - bond_yield
    signal: MarketSignal = MarketSignal.NEUTRAL


class MarketValuation:
    """Compute market-wide valuation indicators and timing signals."""

    def __init__(self, config: dict | None = None, cache: DataCache | None = None):
        cfg = config or {}
        self.timing_cfg = cfg.get("timing", {})
        self.cache = cache

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_snapshot(self) -> MarketSnapshot:
        """Return a full market valuation snapshot."""
        snap = MarketSnapshot()

        # PE
        pe_df = self._fetch_or_cache("market_valuation/pe_ttm", fetch_market_pe_ttm)
        if pe_df is not None and not pe_df.empty:
            snap.pe_percentile = self._extract_percentile(pe_df)
            snap.pe_median = self._extract_median(pe_df)

        # PB
        pb_df = self._fetch_or_cache("market_valuation/pb", fetch_market_pb)
        if pb_df is not None and not pb_df.empty:
            snap.pb_percentile = self._extract_percentile(pb_df)
            snap.pb_median = self._extract_median(pb_df)

        # Bond yield
        bond_yield = fetch_bond_yield_10y()
        if bond_yield is not None:
            snap.bond_yield_10y = bond_yield

        # Yield spread = (1/PE_median) - 10Y bond yield
        if snap.pe_median > 0:
            snap.yield_spread = (1.0 / snap.pe_median * 100) - snap.bond_yield_10y

        # Timing signal
        snap.signal = self._compute_signal(
            snap.pe_percentile, snap.pb_percentile,
        )

        return snap

    def pe_percentile(self) -> float:
        return self.get_snapshot().pe_percentile

    def pb_percentile(self) -> float:
        return self.get_snapshot().pb_percentile

    def composite_market_signal(self) -> MarketSignal:
        return self.get_snapshot().signal

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _fetch_or_cache(self, key: str, fetcher_fn):
        if self.cache:
            cached = self.cache.get(key)
            if cached is not None:
                return cached
        try:
            df = fetcher_fn()
            if self.cache and df is not None:
                self.cache.set(key, df)
            return df
        except Exception:
            logger.warning("Failed to fetch %s", key, exc_info=True)
            return None

    @staticmethod
    def _extract_percentile(df: pd.DataFrame) -> float:
        """Extract the current PE/PB percentile from market data.

        AKShare's stock_a_ttm_lyr / stock_a_all_pb returns columns like
        'quantileInAllHistoryMiddlePeTtm' or similar.
        """
        # Try common column names
        candidates = [
            c for c in df.columns
            if "quantile" in c.lower() or "分位" in c or "百分位" in c
        ]
        if candidates:
            val = df[candidates[0]].iloc[-1]
            return float(val) if not pd.isna(val) else 50.0

        # Fallback: compute from the time series
        value_cols = [
            c for c in df.columns
            if "middle" in c.lower() or "中位数" in c or "TTM" in c or "pe" in c.lower() or "pb" in c.lower()
        ]
        if value_cols:
            series = pd.to_numeric(df[value_cols[0]], errors="coerce").dropna()
            if len(series) > 20:
                current = series.iloc[-1]
                return float((series < current).mean() * 100)

        return 50.0

    @staticmethod
    def _extract_median(df: pd.DataFrame) -> float:
        """Extract the current PE/PB median value."""
        candidates = [
            c for c in df.columns
            if "middle" in c.lower() or "中位数" in c or "TTM" in c
        ]
        if candidates:
            val = df[candidates[0]].iloc[-1]
            return float(val) if not pd.isna(val) else 0.0
        return 0.0

    def _compute_signal(self, pe_pct: float, pb_pct: float) -> MarketSignal:
        pe_low = self.timing_cfg.get("pe_oversold_pct", 30)
        pe_high = self.timing_cfg.get("pe_overbought_pct", 70)
        pe_extreme = self.timing_cfg.get("pe_extreme_pct", 90)

        # Use the same thresholds for PB
        pb_low = pe_low
        pb_high = pe_high
        pb_extreme = pe_extreme

        if pe_pct < pe_low and pb_pct < pb_low:
            return MarketSignal.OVERSOLD
        if pe_pct < pe_low or pb_pct < pb_low:
            return MarketSignal.UNDERVALUED
        if pe_pct > pe_extreme and pb_pct > pe_extreme:
            return MarketSignal.OVERBOUGHT
        if pe_pct > pe_high or pb_pct > pb_high:
            return MarketSignal.OVERVALUED
        return MarketSignal.NEUTRAL
