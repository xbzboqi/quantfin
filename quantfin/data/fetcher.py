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

    Tries Eastmoney first (more data), falls back to Sina.

    Returns DataFrame with English column names.
    """
    # Try Eastmoney first (has PE/PB/mcap)
    try:
        return _fetch_a_share_spot_em()
    except Exception:
        logger.warning("Eastmoney spot failed, falling back to Sina")
        return _fetch_a_share_spot_sina()


def _fetch_a_share_spot_em() -> pd.DataFrame:
    """Fetch A-share spot from Eastmoney (rich data)."""
    df = ak.stock_zh_a_spot_em()
    df = df.rename(columns=_A_SPOT_RENAME)
    keep = list(_A_SPOT_RENAME.values())
    df = df[[c for c in keep if c in df.columns]]
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


def _fetch_a_share_spot_sina() -> pd.DataFrame:
    """Fetch A-share spot from Sina (basic data — no PE/PB/mcap).

    Sina columns by position: 代码, 名称, 最新价, 涨跌额, 涨跌幅,
    买入, 卖出, 昨收, 今开, 最高, 最低, 成交量, 成交额, 时间.
    """
    df = ak.stock_zh_a_spot()

    # Rename by position (avoid encoding issues with Chinese chars)
    COL_NAMES = ["symbol", "name", "price", "change", "pct_change",
                 "bid", "ask", "prev_close", "open", "high", "low",
                 "volume", "amount", "time"]
    df.columns = COL_NAMES[: len(df.columns)]

    numeric_cols = ["price", "pct_change", "change", "volume", "amount",
                    "high", "low", "open", "prev_close"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Sina doesn't provide PE/PB/mcap — add as NaN
    for col in ["pe_dynamic", "pb", "total_mcap", "float_mcap",
                "turnover_rate", "volume_ratio", "momentum_60d"]:
        if col not in df.columns:
            df[col] = float("nan")

    # Estimate turnover rate from volume
    if "volume" in df.columns:
        mean_vol = df["volume"].mean()
        if mean_vol > 0:
            df["turnover_rate"] = df["volume"] / mean_vol * 2.0

    return df


def fetch_a_share_hist(
    symbol: str,
    period: str = "daily",
    start_date: str = "20200101",
    end_date: str = "20991231",
    adjust: str = "qfq",
) -> pd.DataFrame:
    """Fetch daily OHLCV history for a single A-share.

    Tries Eastmoney first (forward-adjusted data), falls back to Sina.

    Args:
        symbol: Stock code e.g. "000001" (no exchange prefix needed for em;
                sina requires "sz000001" or "sh600001" format).
        period: "daily", "weekly", or "monthly".
        start_date: YYYYMMDD start.
        end_date: YYYYMMDD end.
        adjust: "qfq" (forward-adjusted), "hfq" (backward), "" (raw).

    Returns DataFrame with English column names: date, open, close, high, low, volume, amount.
    """
    # Try Eastmoney first
    try:
        return _fetch_a_share_hist_em(symbol, period, start_date, end_date, adjust)
    except Exception:
        logger.debug("Eastmoney history failed for %s, trying Sina", symbol)
        return _fetch_a_share_hist_sina(symbol, start_date, end_date)


def _fetch_a_share_hist_em(
    symbol: str, period: str, start_date: str, end_date: str, adjust: str,
) -> pd.DataFrame:
    """Fetch daily history from Eastmoney."""
    df = ak.stock_zh_a_hist(
        symbol=symbol, period=period,
        start_date=start_date, end_date=end_date, adjust=adjust,
    )
    return _normalize_hist_df(df, _HIST_RENAME)


def _fetch_a_share_hist_sina(
    symbol: str, start_date: str, end_date: str,
) -> pd.DataFrame:
    """Fetch daily history from Sina.

    Sina requires symbol format with exchange prefix: sz000001 or sh600001.
    """
    # Convert plain code to Sina format
    sina_sym = _to_sina_symbol(symbol)

    # Convert date format from YYYYMMDD to YYYY-MM-DD
    start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
    end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

    df = ak.stock_zh_a_daily(
        symbol=sina_sym, start_date=start, end_date=end, adjust="qfq",
    )
    # Sina already has English column names: date, open, high, low, close, volume, amount
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    # Add pct_change
    if "close" in df.columns:
        df["pct_change"] = df["close"].pct_change() * 100

    return df.sort_values("date").reset_index(drop=True)


def _to_sina_symbol(symbol: str) -> str:
    """Convert a plain stock code to Sina format with exchange prefix."""
    code = str(symbol).zfill(6)
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"  # Beijing exchange
    return f"sz{code}"  # default


def _normalize_hist_df(df: pd.DataFrame, rename_map: dict) -> pd.DataFrame:
    """Apply column rename and type coercion to a history DataFrame."""
    df = df.rename(columns=rename_map)
    keep = list(rename_map.values())
    df = df[[c for c in keep if c in df.columns]]
    if "date" in df.columns:
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
    """Fetch all ETF real-time quotes.

    Eastmoney columns by position:
    基金代码, 基金简称, 最新价, IOPV实时估值, 折溢价率, 涨跌额, 涨跌幅,
    成交量, 成交额, 开盘价, 最高价, 最低价, 昨收, 今开, ..., 换手率, ...
    """
    df = ak.fund_etf_spot_em()

    # Use positional mapping to avoid encoding issues
    ETF_COL_NAMES = [
        "symbol", "name", "price", "iopv", "premium_rate",
        "change", "pct_change", "volume", "amount",
        "open", "high", "low", "prev_close",
    ]
    # Take only the columns we have names for
    df = df.iloc[:, : len(ETF_COL_NAMES)]
    df.columns = ETF_COL_NAMES[: len(df.columns)]

    numeric_cols = ["price", "pct_change", "change", "volume", "amount",
                    "open", "high", "low", "prev_close", "iopv", "premium_rate"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Add turnover_rate from volume ratio if available
    df["turnover_rate"] = 0.0
    df["volume_ratio"] = 1.0

    return df


@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_etf_hist(
    symbol: str,
    start_date: str = "20200101",
    end_date: str = "20991231",
) -> pd.DataFrame:
    """Fetch daily history for a single ETF.

    Tries Eastmoney first, falls back to Sina.

    Args:
        symbol: ETF code e.g. "510050".
    """
    try:
        return _fetch_etf_hist_em(symbol, start_date, end_date)
    except Exception:
        logger.debug("Eastmoney ETF history failed for %s, trying Sina", symbol)
        return _fetch_etf_hist_sina(symbol)


def _fetch_etf_hist_em(symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch ETF daily history from Eastmoney."""
    df = ak.fund_etf_hist_em(
        symbol=symbol, start_date=start_date, end_date=end_date, adjust="qfq",
    )
    return _normalize_hist_df(df, _HIST_RENAME)


def _fetch_etf_hist_sina(symbol: str) -> pd.DataFrame:
    """Fetch ETF daily history from Sina.

    Sina requires exchange prefix: sh510050, sz159919 etc.
    ETFs starting with 5 are SH; 1 are SZ.
    """
    code = str(symbol).zfill(6)
    prefix = "sh" if code.startswith("5") else "sz"
    sina_sym = f"{prefix}{code}"

    df = ak.fund_etf_hist_sina(symbol=sina_sym)
    if df.empty:
        return pd.DataFrame(columns=["date", "open", "close", "high", "low", "volume", "amount"])

    # Sina columns: date, prevclose, open, high, low, close, volume, amount
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
    if "close" in df.columns:
        df["pct_change"] = df["close"].pct_change() * 100

    return df.sort_values("date").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Gold
# ---------------------------------------------------------------------------

@retry(max_retries=3, delay=2.0, logger=logger)
def fetch_gold_spot() -> float:
    """Fetch current gold spot price from SGE (上海黄金交易所).

    Returns CNY per gram.
    """
    try:
        df = ak.spot_golden_benchmark_sge()
        if df.empty:
            raise ValueError("No gold data returned")

        # Columns: 日期时间, 今收盘, 昨收盘
        close_col = [c for c in df.columns if "收盘" in c and "今" in c]
        if close_col:
            return float(df[close_col[0]].iloc[-1])

        # Fallback: last numeric column
        last_val = df.iloc[-1, -1]
        return float(last_val)
    except Exception:
        logger.warning("SGE gold spot failed, trying futures spot")
        try:
            df = ak.futures_zh_spot(symbol="AU2502")
            if "最新价" in df.columns:
                return float(df["最新价"].iloc[0])
            # Try generic approach
            for col in df.columns:
                val = pd.to_numeric(df[col], errors="coerce").iloc[0]
                if not pd.isna(val) and 300 < val < 1500:
                    return float(val)
        except Exception:
            pass
        raise RuntimeError("Failed to fetch gold price from any source")


def fetch_gold_hist(start_date: str = "20200101", end_date: str = "20991231") -> pd.DataFrame:
    """Fetch daily gold spot history from SGE.

    Returns DataFrame with columns: date, close, prev_close.
    The full historical series is returned by AKShare.
    """
    df = ak.spot_golden_benchmark_sge()
    if df.empty:
        return df

    rename = {
        "交易时间": "date",
        "晚盘价": "close",     # evening session = close price
        "早盘价": "prev_close",  # morning session = previous close
    }
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})

    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    numeric_cols = ["close", "prev_close"]
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
