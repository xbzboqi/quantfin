"""Unit tests for buy/sell/holding signals."""

import pytest

from quantfin.signals.buy import BuySignal, BuySignalEngine
from quantfin.signals.holding import HoldingClassifier, HoldingPeriod
from quantfin.signals.sell import SellSignal, SellSignalEngine
from quantfin.valuation.market_wide import MarketSignal
from quantfin.valuation.timing import TimingSignal


class TestBuySignal:
    @pytest.fixture
    def engine(self):
        return BuySignalEngine()

    def test_strong_buy_high_score_good_timing(self, engine):
        """Score >= 70 + STRONG_BUY timing → STRONG_BUY."""
        result = engine.evaluate(75.0, TimingSignal.STRONG_BUY)
        assert result == BuySignal.STRONG_BUY

    def test_buy_moderate_score_favorable(self, engine):
        """Score >= 60 + BUY timing → BUY."""
        result = engine.evaluate(65.0, TimingSignal.BUY)
        assert result == BuySignal.BUY

    def test_buy_dip_score(self, engine):
        """Score >= 50 + STRONG_BUY → BUY (buy the dip)."""
        result = engine.evaluate(55.0, TimingSignal.STRONG_BUY)
        assert result == BuySignal.BUY

    def test_watch_borderline(self, engine):
        """Score >= 50 + HOLD → WATCH."""
        result = engine.evaluate(52.0, TimingSignal.HOLD)
        assert result == BuySignal.WATCH

    def test_no_signal_low_score(self, engine):
        """Score < 50 → NO_SIGNAL."""
        result = engine.evaluate(45.0, TimingSignal.STRONG_BUY)
        assert result == BuySignal.NO_SIGNAL

    def test_no_signal_bad_timing(self, engine):
        """Good score but SELL timing → NO_SIGNAL."""
        result = engine.evaluate(80.0, TimingSignal.SELL)
        assert result == BuySignal.NO_SIGNAL


class TestSellSignal:
    @pytest.fixture
    def engine(self):
        return SellSignalEngine({
            "stop_profit": {
                "short_term_return_target": 0.08,
                "medium_term_return_target": 0.15,
                "long_term_return_target": 0.25,
                "score_decline_warning": 0.30,
                "score_decline_exit": 0.50,
            }
        })

    def test_take_profit_short_term(self, engine):
        """Short term return >= 8% → TAKE_PROFIT."""
        result = engine.evaluate(
            position_return=0.10, days_held=60, current_score=80,
            entry_score=75, pe_percentile=40, mid_term_momentum=0.02,
        )
        assert result == SellSignal.TAKE_PROFIT

    def test_take_profit_long_term(self, engine):
        """Long term return >= 25% → TAKE_PROFIT."""
        result = engine.evaluate(
            position_return=0.30, days_held=400, current_score=70,
            entry_score=80, pe_percentile=50, mid_term_momentum=0.05,
        )
        assert result == SellSignal.TAKE_PROFIT

    def test_sell_extreme_pe(self, engine):
        """PE > 95th percentile → SELL."""
        result = engine.evaluate(
            position_return=0.02, days_held=30, current_score=75,
            entry_score=70, pe_percentile=97, mid_term_momentum=0.01,
        )
        assert result == SellSignal.SELL

    def test_reduce_high_pe(self, engine):
        """PE > 85th percentile → REDUCE."""
        result = engine.evaluate(
            position_return=0.03, days_held=50, current_score=70,
            entry_score=70, pe_percentile=88, mid_term_momentum=0.01,
        )
        assert result == SellSignal.REDUCE

    def test_weakening_score_decline(self, engine):
        """Score decline > 30% → WEAKENING."""
        result = engine.evaluate(
            position_return=0.01, days_held=20, current_score=45,
            entry_score=80, pe_percentile=50, mid_term_momentum=0.0,
        )
        assert result == SellSignal.WEAKENING

    def test_sell_score_collapse(self, engine):
        """Score decline > 50% + negative momentum → SELL."""
        result = engine.evaluate(
            position_return=-0.05, days_held=30, current_score=30,
            entry_score=80, pe_percentile=50, mid_term_momentum=-0.08,
        )
        assert result == SellSignal.SELL

    def test_hold_normal(self, engine):
        """Normal situation → HOLD."""
        result = engine.evaluate(
            position_return=0.03, days_held=40, current_score=75,
            entry_score=75, pe_percentile=45, mid_term_momentum=0.01,
        )
        assert result == SellSignal.HOLD

    def test_no_entry_score(self, engine):
        """Without entry score, skip score decline checks."""
        result = engine.evaluate(
            position_return=0.05, days_held=30, current_score=70,
            entry_score=None, pe_percentile=50, mid_term_momentum=0.0,
        )
        assert result == SellSignal.HOLD


class TestHoldingClassifier:
    @pytest.fixture
    def classifier(self):
        return HoldingClassifier()

    def test_long_term(self, classifier):
        """Score >= 70 + OVERSOLD → LONG."""
        result = classifier.classify(75.0, 20.0, MarketSignal.OVERSOLD)
        assert result == HoldingPeriod.LONG

    def test_medium_term(self, classifier):
        """Score >= 60 + UNDERVALUED → MEDIUM."""
        result = classifier.classify(65.0, 25.0, MarketSignal.UNDERVALUED)
        assert result == HoldingPeriod.MEDIUM

    def test_medium_term_high_score_neutral(self, classifier):
        """Score >= 70 + NEUTRAL → MEDIUM."""
        result = classifier.classify(75.0, 50.0, MarketSignal.NEUTRAL)
        assert result == HoldingPeriod.MEDIUM

    def test_short_term(self, classifier):
        """Score >= 50 + OVERSOLD → SHORT."""
        result = classifier.classify(55.0, 20.0, MarketSignal.OVERSOLD)
        assert result == HoldingPeriod.SHORT

    def test_avoid_low_score(self, classifier):
        """Score < 50 → AVOID."""
        result = classifier.classify(45.0, 30.0, MarketSignal.OVERSOLD)
        assert result == HoldingPeriod.AVOID

    def test_short_default(self, classifier):
        """Unclear situation → SHORT."""
        result = classifier.classify(55.0, 55.0, MarketSignal.OVERBOUGHT)
        assert result == HoldingPeriod.SHORT
