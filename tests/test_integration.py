"""End-to-end integration test with mocked data."""

import pandas as pd
import pytest

from quantfin.config import get_default_config
from quantfin.factors.engine import FactorEngine
from quantfin.notify.formatter import ReportFormatter
from quantfin.signals.buy import BuySignal
from quantfin.signals.ranking import RankingEngine
from quantfin.valuation.market_wide import MarketSignal, MarketSnapshot
from quantfin.valuation.timing import TimingSignal


class TestIntegration:
    """Smoke test: run the full pipeline with mock data."""

    def test_full_pipeline_stocks(self, sample_universe):
        """Factor scoring → ranking → report generation works end-to-end."""
        import numpy as np

        cfg = get_default_config()

        # 1. Factor scoring
        engine = FactorEngine(cfg.get("factors"))
        factor_data = {
            "momentum_3m": pd.Series(np.random.uniform(-0.1, 0.3, len(sample_universe))),
            "momentum_12m_1m": pd.Series(np.random.uniform(-0.05, 0.2, len(sample_universe))),
            "pe_percentile": pd.Series(np.random.uniform(0, 100, len(sample_universe))),
            "pb_percentile": pd.Series(np.random.uniform(0, 100, len(sample_universe))),
            "roe": pd.Series(np.random.uniform(5, 25, len(sample_universe))),
            "roe_stability": pd.Series(np.random.uniform(1, 40, len(sample_universe))),
            "gross_margin": pd.Series(np.random.uniform(10, 60, len(sample_universe))),
            "volatility_60d": pd.Series(np.random.uniform(0.1, 0.5, len(sample_universe))),
            "max_drawdown_60d": pd.Series(np.random.uniform(-0.3, -0.01, len(sample_universe))),
            "avg_turnover_20d": pd.Series(np.random.uniform(1, 10, len(sample_universe))),
        }
        scored = engine.score(sample_universe, factor_data)

        assert "composite_score" in scored.columns
        assert not scored["composite_score"].isna().all()

        # 2. Ranking
        ranking = RankingEngine(cfg)
        top = ranking.rank_stocks(
            scored,
            pe_pct_col="pe_percentile_raw",
            pb_pct_col="pb_percentile_raw",
            market_signal=MarketSignal.NEUTRAL,
            top_n=10,
        )
        assert len(top) <= 10
        assert "rank" in top.columns
        assert "buy_signal" in top.columns
        assert "holding" in top.columns

        # Verify signals are valid enum values
        for signal in top["buy_signal"]:
            assert signal in (s.value for s in BuySignal)
        for signal in top["timing"]:
            assert signal in (s.value for s in TimingSignal)

        # 3. Report generation
        snap = MarketSnapshot(
            pe_median=25.5,
            pe_percentile=45.0,
            pb_median=2.1,
            pb_percentile=38.0,
            bond_yield_10y=2.65,
            yield_spread=1.25,
            signal=MarketSignal.NEUTRAL,
        )
        formatter = ReportFormatter()
        report = formatter.format_full_report(
            top_stocks=top,
            top_etfs=None,
            market_snap=snap,
            gold_price=485.0,
        )

        assert "量化分析日报" in report
        assert "市场估值温度" in report
        assert "股票优选" in report
        assert "信号概览" in report
        assert "不构成投资建议" in report

    def test_pipeline_with_etfs(self, sample_universe):
        """ETF pipeline (simplified) works."""
        import numpy as np

        cfg = get_default_config()
        etf_universe = pd.DataFrame({
            "symbol": [f"5100{i:02d}" for i in range(10)],
            "name": [f"ETF_{i}" for i in range(10)],
            "price": np.random.uniform(1, 5, 10),
            "pct_change": np.random.uniform(-2, 3, 10),
            "turnover_rate": np.random.uniform(0.5, 10, 10),
        })

        engine = FactorEngine(cfg.get("factors"))
        factor_data = {
            "momentum_3m": pd.Series(np.random.uniform(-0.1, 0.2, len(etf_universe))),
            "momentum_12m_1m": pd.Series(np.random.uniform(-0.05, 0.15, len(etf_universe))),
            "pe_percentile": pd.Series(np.full(len(etf_universe), 50.0)),
            "pb_percentile": pd.Series(np.full(len(etf_universe), 50.0)),
            "roe": pd.Series(np.full(len(etf_universe), 0.0)),
            "roe_stability": pd.Series(np.full(len(etf_universe), 50.0)),
            "gross_margin": pd.Series(np.full(len(etf_universe), 0.0)),
            "volatility_60d": pd.Series(np.random.uniform(0.1, 0.4, len(etf_universe))),
            "max_drawdown_60d": pd.Series(np.random.uniform(-0.2, -0.01, len(etf_universe))),
            "avg_turnover_20d": pd.Series(np.random.uniform(1, 10, len(etf_universe))),
        }
        scored = engine.score(etf_universe, factor_data)
        ranking = RankingEngine(cfg)
        top = ranking.rank_etfs(scored, market_signal=MarketSignal.UNDERVALUED, top_n=5)

        assert len(top) <= 5
        assert "composite_score" in top.columns
        assert "holding" in top.columns
