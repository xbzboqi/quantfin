"""Value factors: PE/PB percentile, dividend yield, earnings yield."""

from __future__ import annotations

import numpy as np
import pandas as pd


def pe_percentile(current_pe: float, pe_hist: pd.Series | pd.DataFrame) -> float:
    """Percentile rank of current PE within its 5-year history (lower is cheaper).

    Args:
        current_pe: Current PE_TTM value.
        pe_hist: Historical PE series. If DataFrame, uses column named 'pe_ttm' or first numeric.

    Returns 0-100 where 0 means the cheapest (lowest PE) in history.
    """
    if current_pe is None or np.isnan(current_pe):
        return 50.0
    if isinstance(pe_hist, pd.DataFrame):
        cols = [c for c in ["pe_ttm", "PE_TTM"] if c in pe_hist.columns]
        pe_hist = pe_hist[cols[0]] if cols else pe_hist.select_dtypes(include=[np.number]).iloc[:, 0]
    valid = pe_hist.dropna()
    if len(valid) < 20:
        return 50.0
    return float((valid < current_pe).mean() * 100)


def pb_percentile(current_pb: float, pb_hist: pd.Series | pd.DataFrame) -> float:
    """Percentile rank of current PB within its 5-year history (lower is cheaper)."""
    if current_pb is None or np.isnan(current_pb):
        return 50.0
    if isinstance(pb_hist, pd.DataFrame):
        cols = [c for c in ["pb", "PB"] if c in pb_hist.columns]
        pb_hist = pb_hist[cols[0]] if cols else pb_hist.select_dtypes(include=[np.number]).iloc[:, 0]
    valid = pb_hist.dropna()
    if len(valid) < 20:
        return 50.0
    return float((valid < current_pb).mean() * 100)


def pe_percentile_from_spot(row: pd.Series, spot_df: pd.DataFrame) -> float:
    """Estimate PE percentile cross-sectionally using the entire spot market.

    Uses the universe PE distribution to estimate relative cheapness.
    Falls back to this when per-stock history is unavailable.

    Args:
        row: A single stock row with 'pe_dynamic' column.
        spot_df: Full universe spot DataFrame with 'pe_dynamic' column.
    """
    if "pe_dynamic" not in row or "pe_dynamic" not in spot_df.columns:
        return 50.0
    current_pe = row["pe_dynamic"]
    if current_pe <= 0 or pd.isna(current_pe):
        return 50.0
    valid = spot_df["pe_dynamic"].dropna()
    valid = valid[valid > 0]
    if len(valid) < 20:
        return 50.0
    return float((valid < current_pe).mean() * 100)


def pb_percentile_from_spot(row: pd.Series, spot_df: pd.DataFrame) -> float:
    """Estimate PB percentile cross-sectionally from the spot universe."""
    if "pb" not in row or "pb" not in spot_df.columns:
        return 50.0
    current_pb = row["pb"]
    if current_pb <= 0 or pd.isna(current_pb):
        return 50.0
    valid = spot_df["pb"].dropna()
    valid = valid[valid > 0]
    if len(valid) < 20:
        return 50.0
    return float((valid < current_pb).mean() * 100)


def dividend_yield(row: pd.Series) -> float:
    """Estimate dividend yield from available data. Returns 0 if not available."""
    # AKShare spot data doesn't include dividend yield directly,
    # so return a neutral value. Users can extend with stock_financial_abstract.
    return 0.0


def earnings_yield(row: pd.Series) -> float:
    """Earnings yield = 1 / PE. Returns 0 if PE invalid."""
    pe = row.get("pe_dynamic", 0)
    if pe <= 0 or pd.isna(pe):
        return 0.0
    return 1.0 / pe
