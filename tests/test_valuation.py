"""Unit tests for valuation and timing modules."""

import pytest

from quantfin.valuation.market_wide import MarketSignal, MarketValuation
from quantfin.valuation.timing import TimingEngine, TimingSignal


class TestMarketValuation:
    def test_oversold_signal(self):
        """PE < 30 and PB < 30 → OVERSOLD."""
        mv = MarketValuation({"timing": {
            "pe_oversold_pct": 30, "pe_overbought_pct": 70, "pe_extreme_pct": 90,
        }})
        signal = mv._compute_signal(pe_pct=15, pb_pct=20)
        assert signal == MarketSignal.OVERSOLD

    def test_undervalued_signal(self):
        """PE < 30 but PB >= 30 → UNDERVALUED."""
        mv = MarketValuation({"timing": {
            "pe_oversold_pct": 30, "pe_overbought_pct": 70, "pe_extreme_pct": 90,
        }})
        signal = mv._compute_signal(pe_pct=20, pb_pct=40)
        assert signal == MarketSignal.UNDERVALUED

    def test_neutral_signal(self):
        """Both in middle → NEUTRAL."""
        mv = MarketValuation({"timing": {
            "pe_oversold_pct": 30, "pe_overbought_pct": 70, "pe_extreme_pct": 90,
        }})
        signal = mv._compute_signal(pe_pct=50, pb_pct=55)
        assert signal == MarketSignal.NEUTRAL

    def test_overvalued_signal(self):
        """PE > 70 → OVERVALUED."""
        mv = MarketValuation({"timing": {
            "pe_oversold_pct": 30, "pe_overbought_pct": 70, "pe_extreme_pct": 90,
        }})
        signal = mv._compute_signal(pe_pct=80, pb_pct=50)
        assert signal == MarketSignal.OVERVALUED

    def test_overbought_signal(self):
        """Both > 90 → OVERBOUGHT."""
        mv = MarketValuation({"timing": {
            "pe_oversold_pct": 30, "pe_overbought_pct": 70, "pe_extreme_pct": 90,
        }})
        signal = mv._compute_signal(pe_pct=95, pb_pct=92)
        assert signal == MarketSignal.OVERBOUGHT

    def test_custom_thresholds(self):
        """Custom timing thresholds work."""
        mv = MarketValuation({"timing": {
            "pe_oversold_pct": 20, "pe_overbought_pct": 80, "pe_extreme_pct": 95,
        }})
        # At 25%, neither oversold nor overbought with custom config
        signal = mv._compute_signal(pe_pct=25, pb_pct=25)
        assert signal == MarketSignal.NEUTRAL


class TestTimingEngine:
    @pytest.fixture
    def engine(self):
        return TimingEngine()

    def test_strong_buy(self, engine):
        """Market OVERSOLD + stock undervalued → STRONG_BUY."""
        result = engine.evaluate(MarketSignal.OVERSOLD, 15, 20)
        assert result == TimingSignal.STRONG_BUY

    def test_buy_undervalued(self, engine):
        """Market UNDERVALUED + stock undervalued → BUY."""
        result = engine.evaluate(MarketSignal.UNDERVALUED, 20, 25)
        assert result == TimingSignal.BUY

    def test_buy_neutral_cheap(self, engine):
        """Market NEUTRAL + stock undervalued → BUY."""
        result = engine.evaluate(MarketSignal.NEUTRAL, 10, 15)
        assert result == TimingSignal.BUY

    def test_hold_neutral(self, engine):
        """Market NEUTRAL + stock mid → HOLD."""
        result = engine.evaluate(MarketSignal.NEUTRAL, 50, 50)
        assert result == TimingSignal.HOLD

    def test_reduce_overvalued(self, engine):
        """Market OVERVALUED + stock overvalued → REDUCE."""
        result = engine.evaluate(MarketSignal.OVERVALUED, 80, 75)
        assert result == TimingSignal.REDUCE

    def test_sell_overbought(self, engine):
        """Market OVERBOUGHT + stock overvalued → SELL."""
        result = engine.evaluate(MarketSignal.OVERBOUGHT, 85, 90)
        assert result == TimingSignal.SELL

    def test_hold_mixed_signals(self, engine):
        """Stock cheap but market overbought → HOLD (don't buy into froth)."""
        result = engine.evaluate(MarketSignal.OVERBOUGHT, 5, 10)
        assert result == TimingSignal.HOLD
