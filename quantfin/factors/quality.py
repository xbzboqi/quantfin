"""Quality factors: ROE, earnings stability, gross margin, debt ratio."""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_roe(financial_df: pd.DataFrame | None) -> float:
    """Extract the most recent ROE from financial indicator data.

    Looks for ROE-related columns in the abstract financial data.
    Returns ROE as a percentage (e.g., 15.3 for 15.3%).
    """
    if financial_df is None or financial_df.empty:
        return 0.0
    # stock_financial_abstract_ths columns vary; look for ROE patterns
    roe_cols = [c for c in financial_df.columns if "ROE" in c.upper() or "净资产收益率" in c]
    if not roe_cols:
        return 0.0
    val = financial_df[roe_cols[0]].iloc[0]
    try:
        return float(val) if not pd.isna(val) else 0.0
    except (ValueError, TypeError):
        return 0.0


def compute_roe_stability(financial_df: pd.DataFrame | None) -> float:
    """Compute ROE stability as the std dev of quarterly ROE over available history.

    Lower std = more stable. Returns std dev of ROE (percentage points).
    """
    if financial_df is None or financial_df.empty:
        return 50.0  # high uncertainty = worst stability
    roe_cols = [c for c in financial_df.columns if "ROE" in c.upper() or "净资产收益率" in c]
    if not roe_cols:
        return 50.0
    vals = pd.to_numeric(financial_df[roe_cols[0]], errors="coerce").dropna()
    if len(vals) < 2:
        return 50.0
    return float(vals.std())


def compute_gross_margin(financial_df: pd.DataFrame | None) -> float:
    """Extract gross margin from financial indicators.

    Returns gross margin as percentage (e.g., 40.5 for 40.5%).
    """
    if financial_df is None or financial_df.empty:
        return 0.0
    gm_cols = [c for c in financial_df.columns if "毛利率" in c or "gross" in c.lower()]
    if not gm_cols:
        return 0.0
    val = financial_df[gm_cols[0]].iloc[0]
    try:
        return float(val) if not pd.isna(val) else 0.0
    except (ValueError, TypeError):
        return 0.0


def compute_debt_to_equity(financial_df: pd.DataFrame | None) -> float:
    """Extract debt-to-equity ratio (or liability ratio) from financial data."""
    if financial_df is None or financial_df.empty:
        return 50.0  # unknown = assume moderate
    debt_cols = [c for c in financial_df.columns if "负债" in c or "debt" in c.lower() or "杠杆" in c]
    if not debt_cols:
        return 50.0
    val = financial_df[debt_cols[0]].iloc[0]
    try:
        return float(val) if not pd.isna(val) else 50.0
    except (ValueError, TypeError):
        return 50.0


def compute_earnings_growth(financial_df: pd.DataFrame | None) -> float:
    """Estimate YoY earnings growth from financial data.

    Returns growth rate as decimal (e.g., 0.15 = 15% growth).
    """
    if financial_df is None or financial_df.empty:
        return 0.0
    growth_cols = [c for c in financial_df.columns if "增长" in c or "growth" in c.lower()]
    if not growth_cols:
        return 0.0
    val = financial_df[growth_cols[0]].iloc[0]
    try:
        return float(val) / 100.0 if abs(float(val)) > 1 else float(val)
    except (ValueError, TypeError):
        return 0.0
