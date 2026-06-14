"""Shared test fixtures for quantfin."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def sample_price_data() -> pd.DataFrame:
    """Generate 252 days of synthetic OHLCV for a single stock."""
    np.random.seed(42)
    n = 252
    dates = pd.date_range("2025-06-01", periods=n, freq="B")
    base = 10.0
    close = base + np.cumsum(np.random.randn(n) * 0.2)
    close = np.maximum(close, 1.0)
    return pd.DataFrame({
        "date": dates,
        "open": close - np.random.rand(n) * 0.1,
        "close": close,
        "high": close + np.random.rand(n) * 0.2,
        "low": close - np.random.rand(n) * 0.2,
        "volume": np.random.randint(1000000, 10000000, n),
        "amount": np.random.randint(5000000, 50000000, n),
    })


@pytest.fixture
def sample_universe() -> pd.DataFrame:
    """Generate a small 20-stock universe with spot data."""
    np.random.seed(123)
    n = 20
    return pd.DataFrame({
        "symbol": [f"{600000 + i:06d}" for i in range(n)],
        "name": [f"测试股票{i}" for i in range(n)],
        "price": np.random.uniform(5, 50, n),
        "pe_dynamic": np.random.uniform(8, 80, n),
        "pb": np.random.uniform(0.8, 5, n),
        "total_mcap": np.random.uniform(5e9, 2e11, n),
        "float_mcap": np.random.uniform(2e9, 1e11, n),
        "turnover_rate": np.random.uniform(0.5, 8, n),
        "volume_ratio": np.random.uniform(0.5, 2, n),
        "momentum_60d": np.random.uniform(-20, 30, n),
    })


@pytest.fixture
def sample_financial_data() -> pd.DataFrame:
    """Simulated stock_financial_abstract_ths output."""
    return pd.DataFrame({
        "报告期": ["2025-12-31", "2025-09-30", "2025-06-30", "2025-03-31"],
        "净资产收益率(ROE)": [12.5, 9.8, 6.2, 3.1],
        "毛利率": [35.2, 34.8, 34.1, 33.5],
        "资产负债率": [42.1, 41.5, 40.8, 40.2],
        "净利润同比增长率": [15.3, 12.1, 10.5, 8.2],
    })


@pytest.fixture
def sample_market_pe_data() -> pd.DataFrame:
    """Simulated stock_a_ttm_lyr output."""
    n = 100
    return pd.DataFrame({
        "date": pd.date_range("2018-01-01", periods=n, freq="W"),
        "middlePETTM": [15 + i * 0.05 + np.sin(i / 10) * 3 for i in range(n)],
        "quantileInAllHistoryMiddlePeTtm": list(range(5, 105, 1))[:n],
    })


@pytest.fixture
def scored_universe(sample_universe) -> pd.DataFrame:
    """Sample universe with composite_score and factor columns added."""
    np.random.seed(77)
    df = sample_universe.copy()
    df["composite_score"] = np.random.uniform(30, 95, len(df))
    df["pe_percentile_raw"] = np.random.uniform(0, 100, len(df))
    df["pb_percentile_raw"] = np.random.uniform(0, 100, len(df))
    return df


@pytest.fixture
def temp_cache_dir(tmp_path) -> str:
    """Temporary cache directory."""
    d = tmp_path / "cache"
    d.mkdir()
    return str(d)
