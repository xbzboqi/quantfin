"""Individual stock valuation: PE/PB percentile vs own history."""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from quantfin.data.cache import DataCache
from quantfin.data.fetcher import fetch_a_share_pe_pb_hist
from quantfin.factors.value import pe_percentile, pb_percentile

logger = logging.getLogger(__name__)

# Fallback to cross-sectional percentile when historical data is unavailable
from quantfin.factors.value import pe_percentile_from_spot, pb_percentile_from_spot  # noqa: E402


class IndividualValuation:
    """Per-stock valuation using historical PE/PB percentile."""

    def __init__(self, cache: DataCache | None = None):
        self.cache = cache

    def pe_pct(self, symbol: str, spot_row: pd.Series | None = None,
               spot_df: pd.DataFrame | None = None) -> float:
        """Get PE percentile for a single stock.

        Tries historical PE data first; falls back to cross-sectional percentile.
        """
        pe_hist = self._get_pe_pb_hist(symbol)
        if pe_hist is not None and not pe_hist.empty:
            # Find current PE
            pe_col = [c for c in ["pe_ttm", "pe", "PE"] if c in pe_hist.columns]
            if pe_col and spot_row is not None and "pe_dynamic" in spot_row:
                return pe_percentile(spot_row["pe_dynamic"], pe_hist[pe_col[0]])
            # If no spot_row, use last value in series
            if pe_col:
                series = pd.to_numeric(pe_hist[pe_col[0]], errors="coerce").dropna()
                if len(series) > 20:
                    current = series.iloc[-1]
                    return float((series < current).mean() * 100)

        # Fallback to cross-sectional
        if spot_row is not None and spot_df is not None:
            return pe_percentile_from_spot(spot_row, spot_df)
        return 50.0

    def pb_pct(self, symbol: str, spot_row: pd.Series | None = None,
               spot_df: pd.DataFrame | None = None) -> float:
        """Get PB percentile for a single stock."""
        pe_hist = self._get_pe_pb_hist(symbol)
        if pe_hist is not None and not pe_hist.empty:
            pb_col = [c for c in ["pb", "PB"] if c in pe_hist.columns]
            if pb_col and spot_row is not None and "pb" in spot_row:
                return pb_percentile(spot_row["pb"], pe_hist[pb_col[0]])
            if pb_col:
                series = pd.to_numeric(pe_hist[pb_col[0]], errors="coerce").dropna()
                if len(series) > 20:
                    current = series.iloc[-1]
                    return float((series < current).mean() * 100)

        if spot_row is not None and spot_df is not None:
            return pb_percentile_from_spot(spot_row, spot_df)
        return 50.0

    def is_undervalued(self, symbol: str, spot_row: pd.Series | None = None,
                       spot_df: pd.DataFrame | None = None) -> bool:
        """True if both PE and PB are below 30th percentile."""
        pe = self.pe_pct(symbol, spot_row, spot_df)
        pb = self.pb_pct(symbol, spot_row, spot_df)
        return pe < 30 and pb < 30

    def is_overvalued(self, symbol: str, spot_row: pd.Series | None = None,
                      spot_df: pd.DataFrame | None = None) -> bool:
        """True if either PE or PB is above 70th percentile."""
        pe = self.pe_pct(symbol, spot_row, spot_df)
        pb = self.pb_pct(symbol, spot_row, spot_df)
        return pe > 70 or pb > 70

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _get_pe_pb_hist(self, symbol: str) -> pd.DataFrame | None:
        cache_key = f"pe_pb_hist/{symbol}"
        if self.cache:
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached
        try:
            df = fetch_a_share_pe_pb_hist(symbol)
            if self.cache and df is not None and not df.empty:
                self.cache.set(cache_key, df)
            return df
        except Exception:
            logger.debug("No PE/PB history for %s (may be a new stock)", symbol)
            return None
