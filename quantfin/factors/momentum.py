"""Momentum factors: multi-horizon price momentum and RSI."""

from __future__ import annotations

import numpy as np
import pandas as pd


def momentum_n(df: pd.DataFrame, n_days: int = 60) -> pd.Series:
    """Price momentum over *n_days*: (close_today - close_Nd_ago) / close_Nd_ago.

    Expects DataFrame with at least a 'close' column, sorted by date ascending.
    Returns a Series aligned to the last row of each group.
    """
    return df["close"].pct_change(periods=n_days).iloc[-1] if len(df) > n_days else np.nan


def momentum_1m(df: pd.DataFrame) -> float:
    """20-day (~1 month) momentum."""
    return momentum_n(df, 20)


def momentum_3m(df: pd.DataFrame) -> float:
    """60-day (~3 month) momentum."""
    return momentum_n(df, 60)


def momentum_6m(df: pd.DataFrame) -> float:
    """120-day (~6 month) momentum."""
    return momentum_n(df, 120)


def momentum_12m_1m(df: pd.DataFrame) -> float:
    """12-month momentum excluding the most recent month (Carhart).

    Returns: (close_12m_ago - close_1m_ago) / close_1m_ago
    """
    if len(df) < 252:
        return np.nan
    close_12m_ago = df["close"].iloc[-252]
    close_1m_ago = df["close"].iloc[-20]
    return (close_1m_ago - close_12m_ago) / close_12m_ago if close_12m_ago != 0 else np.nan


def rsi_14(df: pd.DataFrame) -> float:
    """RSI(14) oscillator value. Returns 0-100."""
    if len(df) < 15:
        return 50.0
    delta = df["close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0
