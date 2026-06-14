"""Volatility factors: historical vol, beta, max drawdown, downside deviation."""

from __future__ import annotations

import numpy as np
import pandas as pd


def volatility_60d(df: pd.DataFrame) -> float:
    """Annualized volatility from 60-day daily returns (lower = more stable)."""
    if len(df) < 60:
        return np.nan
    daily_ret = df["close"].pct_change().dropna().tail(60)
    return float(daily_ret.std() * np.sqrt(252))


def max_drawdown_60d(df: pd.DataFrame) -> float:
    """Maximum peak-to-trough drawdown over the last 60 days.

    Returns a positive decimal (e.g., 0.15 = 15% drawdown).
    """
    if len(df) < 60:
        return np.nan
    close = df["close"].tail(60)
    peak = close.expanding().max()
    drawdown = (close - peak) / peak
    return float(drawdown.min())


def downside_deviation_60d(df: pd.DataFrame) -> float:
    """Standard deviation of negative daily returns only (60-day).

    Annualized.
    """
    if len(df) < 60:
        return np.nan
    daily_ret = df["close"].pct_change().dropna().tail(60)
    negative = daily_ret[daily_ret < 0]
    if len(negative) < 5:
        return 0.0
    return float(negative.std() * np.sqrt(252))


def beta_60d(df: pd.DataFrame, market_df: pd.DataFrame | None = None) -> float:
    """CAPM beta vs the market (CSI 300 proxy) over 60 days.

    If market_df is None, returns NaN (caller should provide market data).
    """
    if len(df) < 60 or market_df is None or len(market_df) < 60:
        return np.nan
    stock_ret = df["close"].pct_change().dropna().tail(60)
    market_ret = market_df["close"].pct_change().dropna()
    # Align by date
    aligned = pd.concat([stock_ret.rename("stock"), market_ret.rename("market")], axis=1).dropna()
    if len(aligned) < 20:
        return np.nan
    cov = aligned.cov()
    if "stock" not in cov.columns or "market" not in cov.columns:
        return np.nan
    return float(cov.loc["stock", "market"] / cov.loc["market", "market"])
