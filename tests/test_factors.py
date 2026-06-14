"""Unit tests for factor computations and the factor engine."""

import numpy as np
import pandas as pd
import pytest

from quantfin.factors import momentum, value, volatility, liquidity, quality
from quantfin.factors.engine import FactorEngine


class TestMomentum:
    def test_momentum_3m_positive_return(self, sample_price_data):
        """3-month momentum positive for an upward trend."""
        df = sample_price_data.copy()
        # Create a clear upward trend over last 60 days
        df.loc[df.index[-60:], "close"] = df["close"].iloc[-1] * 1.15  # ~15% up
        result = momentum.momentum_3m(df)
        assert result > 0

    def test_momentum_n_with_insufficient_data(self):
        """Momentum returns NaN when not enough data."""
        df = pd.DataFrame({"close": [10, 10.5, 10.2]})
        result = momentum.momentum_n(df, 20)
        assert np.isnan(result)

    def test_rsi_14_range(self, sample_price_data):
        """RSI should be between 0 and 100."""
        rsi = momentum.rsi_14(sample_price_data)
        assert 0 <= rsi <= 100

    def test_rsi_14_minimum_data(self):
        """RSI returns 50 when insufficient data."""
        df = pd.DataFrame({"close": [10, 11, 10.5, 11.2, 10.8]})
        rsi = momentum.rsi_14(df)
        # With < 15 rows, returns 50
        assert rsi == 50.0


class TestValue:
    def test_pe_percentile_cheap(self):
        """PE in the bottom quartile should return low percentile."""
        pe_hist = pd.Series(np.random.uniform(15, 30, 100))
        current_pe = 5.0  # Well below the minimum
        result = value.pe_percentile(current_pe, pe_hist)
        assert result < 10

    def test_pe_percentile_expensive(self):
        """PE in the top quartile should return high percentile."""
        pe_hist = pd.Series(np.random.uniform(15, 30, 100))
        current_pe = 50.0  # Well above the maximum
        result = value.pe_percentile(current_pe, pe_hist)
        assert result > 90

    def test_pe_percentile_nan_fallback(self):
        """NaN PE returns 50 (neutral)."""
        result = value.pe_percentile(np.nan, pd.Series([10, 20, 30]))
        assert result == 50.0

    def test_pe_percentile_from_spot(self, sample_universe):
        """Cross-sectional PE percentile."""
        row = sample_universe.iloc[0]
        result = value.pe_percentile_from_spot(row, sample_universe)
        assert 0 <= result <= 100

    def test_earnings_yield(self):
        """Earnings yield = 1/PE."""
        row = pd.Series({"pe_dynamic": 20})
        assert value.earnings_yield(row) == pytest.approx(0.05)


class TestVolatility:
    def test_volatility_60d_positive(self, sample_price_data):
        """Volatility should be positive with price movement."""
        vol = volatility.volatility_60d(sample_price_data)
        assert vol > 0

    def test_max_drawdown_negative(self, sample_price_data):
        """Max drawdown should be <= 0 (negative percentage)."""
        drawdown = volatility.max_drawdown_60d(sample_price_data)
        assert drawdown <= 0

    def test_max_drawdown_with_crash(self, sample_price_data):
        """Drawdown captures a sharp decline."""
        df = sample_price_data.copy()
        # Insert a sharp 30% crash in the last 20 days
        df.loc[df.index[-20:], "close"] = df["close"].iloc[-21] * 0.7
        drawdown = volatility.max_drawdown_60d(df)
        assert drawdown < -0.25  # ~30% drawdown


class TestQuality:
    def test_compute_roe(self, sample_financial_data):
        """ROE extracted from financial indicators."""
        roe = quality.compute_roe(sample_financial_data)
        assert roe == 12.5

    def test_compute_gross_margin(self, sample_financial_data):
        """Gross margin extracted."""
        gm = quality.compute_gross_margin(sample_financial_data)
        assert gm == 35.2

    def test_compute_roe_stability(self, sample_financial_data):
        """ROE stability = std dev of quarterly ROE."""
        stab = quality.compute_roe_stability(sample_financial_data)
        assert 0 < stab < 50  # Should be moderate

    def test_empty_financial_fallback(self):
        """Empty data returns safe defaults."""
        assert quality.compute_roe(None) == 0.0
        assert quality.compute_roe_stability(None) == 50.0
        assert quality.compute_gross_margin(None) == 0.0


class TestLiquidity:
    def test_avg_turnover_rate(self, sample_universe):
        """Average turnover rate from spot data."""
        row = sample_universe.iloc[0]
        rate = liquidity.avg_turnover_rate(row)
        assert rate > 0

    def test_avg_volume_ratio(self, sample_universe):
        """Volume ratio from spot data."""
        row = sample_universe.iloc[0]
        r = liquidity.avg_volume_ratio(row)
        assert r > 0


class TestFactorEngine:
    def test_scoring_output_columns(self, sample_universe):
        """Scoring adds expected columns."""
        engine = FactorEngine()
        factor_data = {
            "momentum_3m": pd.Series(np.random.uniform(-0.1, 0.3, len(sample_universe))),
            "pe_percentile": pd.Series(np.random.uniform(0, 100, len(sample_universe))),
            "roe": pd.Series(np.random.uniform(5, 25, len(sample_universe))),
            "volatility_60d": pd.Series(np.random.uniform(0.1, 0.5, len(sample_universe))),
            "avg_turnover_20d": pd.Series(np.random.uniform(1, 10, len(sample_universe))),
        }
        result = engine.score(sample_universe, factor_data)
        assert "composite_score" in result.columns
        assert "composite_zscore" in result.columns
        for name in factor_data:
            assert f"{name}_raw" in result.columns
            assert f"{name}_zscore" in result.columns

    def test_composite_score_range(self, sample_universe):
        """Composite score should be in 0-100 range."""
        engine = FactorEngine()
        n = len(sample_universe)
        factor_data = {
            "momentum_3m": pd.Series(np.random.uniform(-0.2, 0.4, n)),
            "pe_percentile": pd.Series(np.random.uniform(0, 100, n)),
            "roe": pd.Series(np.random.uniform(5, 30, n)),
        }
        result = engine.score(sample_universe, factor_data)
        scores = result["composite_score"].dropna()
        assert scores.min() >= 0
        assert scores.max() <= 100

    def test_negative_direction_flipped(self, sample_universe):
        """Negative factors get flipped sign after z-score."""
        engine = FactorEngine()
        n = len(sample_universe)
        # pe_percentile is negative direction (lower is better)
        # Create pe_pct where stock 0 is cheapest (pct=10%) and stock 19 is expensive (pct=90%)
        pe_pct = pd.Series(np.linspace(10, 90, n))
        factor_data = {"pe_percentile": pe_pct}
        result = engine.score(sample_universe, factor_data)
        # Cheapest stock (stock 0) should have higher z-score than expensive stock (stock 19)
        z_0 = result.loc[0, "pe_percentile_zscore"]
        z_19 = result.loc[19, "pe_percentile_zscore"]
        assert z_0 > z_19, "Cheap stock should have higher z-score after flipping"

    def test_weight_normalization(self, sample_universe):
        """Custom weights apply correctly."""
        weights = {
            "momentum_3m": 0.5,
            "pe_percentile": 0.3,
            "roe": 0.2,
        }
        engine = FactorEngine({"weights": weights, "winsorize_quantiles": [0.01, 0.99]})
        n = len(sample_universe)
        factor_data = {
            "momentum_3m": pd.Series(np.ones(n) * 0.1),
            "pe_percentile": pd.Series(np.ones(n) * 50),
            "roe": pd.Series(np.ones(n) * 15),
        }
        result = engine.score(sample_universe, factor_data)
        # With all equal values, all z-scores are 0, so composite is 50
        assert result["composite_score"].iloc[0] == pytest.approx(50.0, abs=5)
