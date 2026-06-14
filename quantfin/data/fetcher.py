"""Unified AKShare data fetching layer.

All external data flows through this module. Each function returns a
pandas.DataFrame with English column names for downstream consistency.
"""

from __future__ import annotations

import logging
from typing import Optional

import akshare as ak
import pandas as pd

from quantfin.utils import retry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name mappings (AKShare Chinese → English)
# ---------------------------------------------------------------------------

_A_SPOT_RENAME = {
    "代码": "symbol",
    "名称": "name",
    "最新价": "price",
    "涨跌幅": "pct_change",
    "涨跌额": "change",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "最高": "high",
    "最低": "low",
    "今开": "open",
    "昨收": "prev_close",
    "量比": "volume_ratio",
    "换手率": "turnover_rate",
    "市盈率-动态": "pe_dynamic",
    "市净率": "pb",
    "总市值": "total_mcap",
    "流通市值": "float_mcap",
    "60日涨跌幅": "momentum_60d",
}

_HIST_RENAME = {
    "日期": "date",
    "开盘": "open",
    "收盘": "close",
    "最高": "high",
    "最低": "low",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "涨跌幅": "pct_change",
    "涨跌额": "change",
    "换手率": "turnover_rate",
}

_ETF_SPOT_RENAME = {
    "基金代码": "symbol",
    "基金简称": "name",
    "最新价": "price",
    "涨跌幅": "pct_change",
    "成交量": "volume",
    "成交额": "amount",
    "换手率": "turnover_rate",
    "量比": "volume_ratio",
    "IOPV": "iopv",
}

_GOLD_RENAME = {
    "日期": "date",
    "开盘价": "open",
    "收盘价": "close",
    "最高价": "high",
    "最低价": "low",
    "成交量": "volume",
    "昨结算": "prev_close",
}

# ---------------------------------------------------------------------------
# A-Share / Stock data
# ---------------------------------------------------------------------------

@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_a_share_spot() -> pd.DataFrame:
    """Fetch all A-share real-time quotes with PE/PB/mcap.

    Returns DataFrame with English column names.
    """
    df = ak.stock_zh_a_spot_em()
    df = df.rename(columns=_A_SPOT_RENAME)
    # Keep only columns we renamed (drop leftovers)
    keep = list(_A_SPOT_RENAME.values())
    df = df[[c for c in keep if c in df.columns]]
    # Convert numeric columns
    numeric_cols = [
        "price", "pct_change", "change", "volume", "amount",
        "amplitude", "high", "low", "open", "prev_close",
        "volume_ratio", "turnover_rate", "pe_dynamic", "pb",
        "total_mcap", "float_mcap", "momentum_60d",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_a_share_hist(
    symbol: str,
    period: str = "daily",
    start_date: str = "20200101",
    end_date: str = "20991231",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """Fetch daily OHLCV history for a single A-share.

    Args:
        symbol: Stock code e.g. "000001" (no exchange prefix).
        period: "daily", "weekly", or "monthly".
        start_date: YYYYMMDD start.
        end_date: YYYYMMDD end.
        adjust: "qfq" (forward-adjusted), "hfq" (backward), "" (raw).

    Returns DataFrame with English column names.
    """
    df = ak.stock_zh_a_hist(
        symbol=symbol, period=period,
        start_date=start_date, end_date=end_date, adjust=adjust,
    )
    df = df.rename(columns=_HIST_RENAME)
    keep = list(_HIST_RENAME.values())
    df = df[[c for c in keep if c in df.columns]]
    df["date"] = pd.to_datetime(df["date"])
    numeric_cols = [
        "open", "close", "high", "low", "volume", "amount",
        "amplitude", "pct_change", "change", "turnover_rate",
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_a_share_pe_pb_hist(symbol: str) -> pd.DataFrame:
    """Fetch historical PE/PB series for a single stock.

    Uses AKShare's stock_a_lg_indicator (Lixinger data provider).

    Returns DataFrame with columns: date, pe_ttm, pb.
    """
    df = ak.stock_a_lg_indicator(symbol=symbol)
    # Rename known columns
    rename = {
        "tradeDate": "date",
        "pe": "pe_ttm",
        "pb": "pb",
        "pettm": "pe",  # some versions
    }
    df = df.rename(columns={
        k: v for k, v in rename.items() if k in df.columns
    })
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_market_pe_ttm() -> pd.DataFrame:
    """Fetch A-share TTM PE (all-market level).

    Returns DataFrame with columns including:
      date, middlePETTM, quantileInAllHistoryMiddlePeTtm, etc.
    """
    try:
        df = ak.stock_a_ttm_lyr()
    except Exception:
        # Fallback: use another interface
        df = ak.stock_a_pe_lg()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_market_pb() -> pd.DataFrame:
    """Fetch A-share PB (all-market level)."""
    try:
        df = ak.stock_a_all_pb()
    except Exception:
        df = ak.stock_a_pb_lg()
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    return df


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_financial_indicator(symbol: str) -> Optional[pd.DataFrame]:
    """Fetch financial indicators (ROE, gross margin, debt ratio) for a stock.

    Uses stock_financial_abstract_ths (东方财富 abstract).
    """
    try:
        df = ak.stock_financial_abstract_ths(symbol=symbol, indicator="按报告期")
    except Exception:
        return None
    if df is None or df.empty:
        return None
    return df


# ---------------------------------------------------------------------------
# ETF / Fund data
# ---------------------------------------------------------------------------

@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_etf_spot() -> pd.DataFrame:
    """Fetch all ETF real-time quotes."""
    df = ak.fund_etf_spot_em()
    df = df.rename(columns=_ETF_SPOT_RENAME)
    keep = list(_ETF_SPOT_RENAME.values())
    df = df[[c for c in keep if c in df.columns]]
    numeric_cols = ["price", "pct_change", "volume", "amount", "turnover_rate", "volume_ratio", "iopv"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_etf_hist(
    symbol: str,
    start_date: str = "20200101",
    end_date: str = "20991231",
) -> pd.DataFrame:
    """Fetch daily history for a single ETF."""
    df = ak.fund_etf_hist_em(
        symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq",
    )
    df = df.rename(columns=_HIST_RENAME)
    keep = list(_HIST_RENAME.values())
    df = df[[c for c in keep if c in df.columns]]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    numeric_cols = ["open", "close", "high", "low", "volume", "amount", "pct_change", "turnover_rate"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Gold
# ---------------------------------------------------------------------------

@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_gold_spot() -> float:
    """Fetch current gold futures spot price (AU2502 / most-active contract).

    Returns CNY per gram (approximate).
    """
    try:
        df = ak.futures_zh_spot_sina(symbol="AU0")
    except Exception:
        # Fallback to gold spot from sina
        df = ak.spot_golden_benchmark_sina()
        if "最新价" in df.columns:
            return float(df["最新价"].iloc[-1])
        raise

    # AU0 returns the most-active gold futures contract
    if "price" in df.columns or "最新价" in df.columns:
        col = "price" if "price" in df.columns else "最新价"
        return float(df[col].iloc[0])
    # Try to find the AU-prefixed row
    gold_row = df[df["symbol"].str.startswith("AU")].iloc[0] if "symbol" in df.columns else df.iloc[0]
    if "price" in gold_row:
        return float(gold_row["price"])
    return float(gold_row.iloc[1])  # best effort


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_gold_hist(start_date: str = "20200101", end_date: str = "20991231") -> pd.DataFrame:
    """Fetch daily gold futures history."""
    df = ak.futures_zh_daily_sina(symbol="AU2502")
    df = df.rename(columns=_GOLD_RENAME)
    keep = list(_GOLD_RENAME.values())
    df = df[[c for c in keep if c in df.columns]]
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    numeric_cols = ["open", "close", "high", "low", "volume", "prev_close"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Bond yield
# ---------------------------------------------------------------------------

@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_bond_yield_10y() -> Optional[float]:
    """Fetch the latest China 10-year government bond yield."""
    try:
        df = ak.bond_china_yield()
        # The DataFrame has columns: date, 10Y yield, etc.
        bond_col = [c for c in df.columns if "10" in c or "十年" in c]
        if bond_col and not df.empty:
            return float(df[bond_col[0]].iloc[-1])
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Batch helper
# ---------------------------------------------------------------------------

def fetch_hist_batch(
    symbols: list[str],
    data_type: str = "stock",
    start_date: str = "20210101",
) -> dict[str, pd.DataFrame]:
    """Fetch daily history for a batch of symbols.

    Args:
        symbols: List of stock/ETF codes.
        data_type: "stock" or "etf".
        start_date: YYYYMMDD start.

    Returns dict[symbol] -> DataFrame. Failed symbols are skipped with warning.
    """
    result = {}
    fetcher = fetch_a_share_hist if data_type == "stock" else fetch_etf_hist
    for sym in symbols:
        try:
            df = fetcher(symbol=sym, start_date=start_date)
            if not df.empty:
                result[sym] = df
        except Exception:
            logger.warning("Failed to fetch history for %s", sym)
    return result
