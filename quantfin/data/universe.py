"""Stock and ETF universe builder with quality filters."""

from __future__ import annotations

import logging
from typing import Optional

import pandas as pd

from quantfin.data.cache import DataCache
from quantfin.data.fetcher import fetch_a_share_spot, fetch_etf_spot

logger = logging.getLogger(__name__)


ST_PATTERNS = ["ST", "*ST", "退市", "N ", "C "]
ETF_EXCLUDE_KEYWORDS = ["分级", "两倍", "三倍", "做空", "反向", "杠杆"]


class UniverseBuilder:
    """Builds filtered investment universe for stocks and ETFs."""

    def __init__(self, config: dict, cache: Optional[DataCache] = None):
        self.config = config.get("universe", {})
        self.cache = cache

    # ------------------------------------------------------------------
    # Stock Universe
    # ------------------------------------------------------------------

    def build_stock_universe(self, force_refresh: bool = False) -> pd.DataFrame:
        """Build filtered A-share universe.

        Filters:
        1. Remove ST / *ST / delisting / new-IPO stocks
        2. Remove stocks listed < min_listing_days
        3. Remove stocks with PE <= 0 or PE > max_pe
        4. Remove stocks with avg daily turnover < min threshold

        Returns DataFrame with columns: symbol, name, price, pe_dynamic, pb,
            total_mcap, float_mcap, turnover_rate, momentum_60d.
        """
        if self.cache and not force_refresh:
            cached = self.cache.get("universe/a_share")
            if cached is not None:
                return cached

        logger.info("Building stock universe...")
        df = fetch_a_share_spot()
        initial = len(df)
        logger.info("Fetched %d A-shares (raw)", initial)

        # 1. Remove ST / *ST / delisting
        df = self._exclude_st(df)

        # 2. Remove extreme PE
        df = self._filter_pe(df)

        # 3. Remove illiquid stocks
        df = self._filter_liquidity(df)

        # 4. Keep essential columns
        keep_cols = _intersect_columns(df, [
            "symbol", "name", "price", "pe_dynamic", "pb",
            "total_mcap", "float_mcap", "turnover_rate",
            "momentum_60d", "pct_change", "volume", "amount", "volume_ratio",
        ])
        df = df[keep_cols].reset_index(drop=True)

        logger.info("Universe: %d stocks after filtering (removed %d)", len(df), initial - len(df))

        if self.cache:
            self.cache.set("universe/a_share", df)

        return df

    # ------------------------------------------------------------------
    # ETF Universe
    # ------------------------------------------------------------------

    def build_etf_universe(self, force_refresh: bool = False) -> pd.DataFrame:
        """Build filtered ETF universe.

        Filters:
        1. Remove leveraged / inverse ETFs
        2. Remove ETFs with AUM < min_etf_aum (estimated as price * volume)
        3. Remove ETFs trading < min_listing_days (approximation)

        Returns DataFrame with columns: symbol, name, price, pct_change,
            volume, amount, turnover_rate.
        """
        if self.cache and not force_refresh:
            cached = self.cache.get("universe/etf")
            if cached is not None:
                return cached

        logger.info("Building ETF universe...")
        df = fetch_etf_spot()
        initial = len(df)
        logger.info("Fetched %d ETFs (raw)", initial)

        # 1. Remove leveraged / inverse ETFs
        df = self._exclude_etf_keywords(df)

        # 2. Estimate AUM filter (use volume * price as rough proxy)
        if "amount" in df.columns:
            min_amount = self.config.get("min_etf_aum", 100_000_000)
            # amount is daily turnover, keep ETFs with reasonable activity
            df = df[df["amount"] >= min_amount / 20].copy()  # rough proxy

        keep_cols = _intersect_columns(df, [
            "symbol", "name", "price", "pct_change",
            "volume", "amount", "turnover_rate", "volume_ratio",
        ])
        df = df[keep_cols].reset_index(drop=True)

        logger.info("ETF universe: %d ETFs after filtering (removed %d)", len(df), initial - len(df))

        if self.cache:
            self.cache.set("universe/etf", df)

        return df

    # ------------------------------------------------------------------
    # Internal filters
    # ------------------------------------------------------------------

    def _exclude_st(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove ST, *ST, delisting, and new IPO stocks by name pattern."""
        if not self.config.get("exclude_st", True):
            return df
        mask = pd.Series(True, index=df.index)
        for pat in ST_PATTERNS:
            if "name" in df.columns:
                mask &= ~df["name"].str.contains(pat, na=False)
        return df[mask]

    def _filter_pe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove stocks with non-positive or extreme PE."""
        if "pe_dynamic" not in df.columns:
            return df
        max_pe = self.config.get("max_pe", 200)
        mask = (df["pe_dynamic"] > 0) & (df["pe_dynamic"] <= max_pe)
        return df[mask]

    def _filter_liquidity(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove stocks with average daily turnover below threshold."""
        if "amount" not in df.columns:
            return df
        min_amount = self.config.get("min_daily_turnover_cny", 10_000_000)
        return df[df["amount"] >= min_amount].copy()

    def _exclude_etf_keywords(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove leveraged/inverse ETFs by name keyword."""
        mask = pd.Series(True, index=df.index)
        for kw in ETF_EXCLUDE_KEYWORDS:
            if "name" in df.columns:
                mask &= ~df["name"].str.contains(kw, na=False)
        return df[mask]


def _intersect_columns(df: pd.DataFrame, desired: list[str]) -> list[str]:
    """Return columns from `desired` that actually exist in `df`."""
    return [c for c in desired if c in df.columns]
