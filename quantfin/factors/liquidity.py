"""Liquidity factors: average turnover, volume ratio, Amihud illiquidity."""

from __future__ import annotations

import numpy as np
import pandas as pd


def avg_turnover_rate(row: pd.Series) -> float:
    """Return turnover_rate from spot data as-is (already reflects recent trading).

    Falls back to 0 if not present.
    """
    val = row.get("turnover_rate", 0.0)
    try:
        return float(val) if not pd.isna(val) else 0.0
    except (ValueError, TypeError):
        return 0.0


def avg_volume_ratio(row: pd.Series) -> float:
    """Volume ratio = current_volume / avg_volume, available in spot data."""
    val = row.get("volume_ratio", 1.0)
    try:
        return float(val) if not pd.isna(val) else 1.0
    except (ValueError, TypeError):
        return 1.0


def amihud_illiquidity_20d(df: pd.DataFrame) -> float:
    """Amihud illiquidity measure over 20 days.

    mean(|daily_return| / daily_amount). Higher = more illiquid.

    Returns NaN if insufficient data.
    """
    if len(df) < 20:
        return np.nan
    ret = df["close"].pct_change().dropna().tail(20)
    if "amount" not in df.columns:
        # Use volume as proxy
        vol = df["volume"].tail(20).reset_index(drop=True)
        # Scale down to avoid tiny numbers
        illiq = np.mean(np.abs(ret.values) / (vol.values / 1e8 + 1))
    else:
        amount = df["amount"].tail(20).reset_index(drop=True)
        illiq = np.mean(np.abs(ret.values) / (amount.values + 1))
    return float(illiq)
