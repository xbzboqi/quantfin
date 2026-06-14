"""Factor Engine: z-score normalization, weighted composite scoring."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sp_stats

logger = logging.getLogger(__name__)


class FactorEngine:
    """Multi-factor scoring engine.

    For each factor:
    1. Compute raw values across the universe
    2. Winsorize at specified quantiles
    3. Z-score normalize
    4. Flip sign for "negative" direction factors
    5. Weighted sum → composite score (0-100)
    """

    def __init__(self, config: dict[str, Any] | None = None):
        cfg = config or {}
        self.weights = cfg.get("weights", _default_weights())
        self.winsorize_q = tuple(cfg.get("winsorize_quantiles", [0.01, 0.99]))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score(
        self,
        universe: pd.DataFrame,
        factor_data: dict[str, pd.Series],
    ) -> pd.DataFrame:
        """Compute composite scores for the universe.

        Args:
            universe: DataFrame with one row per stock/ETF (must have 'symbol').
            factor_data: Dict mapping factor_name → pd.Series of raw values,
                         indexed by symbol (or position-aligned with universe).

        Returns:
            The universe DataFrame with added columns:
            - {name}_raw, {name}_zscore for each factor
            - composite_zscore (weighted average z-score)
            - composite_score (0-100 percentile rank)
        """
        result = universe.copy()
        z_scores = {}

        # ── Step 1-3: Compute z-scores per factor ──
        for name, raw in factor_data.items():
            direction = _FACTOR_DIRECTIONS.get(name, "positive")
            raw_name = f"{name}_raw"
            z_name = f"{name}_zscore"

            # Align raw values to universe index
            if hasattr(raw, "values"):
                result[raw_name] = raw.values if len(raw) == len(result) else np.nan
            else:
                result[raw_name] = raw

            # Winsorize then z-score
            z = self._winsorize_and_zscore(result[raw_name])
            # Flip for negative-direction factors
            if direction == "negative":
                z = -z
            result[z_name] = z
            z_scores[name] = z

        # ── Step 4: Weighted composite ──
        composite = pd.Series(0.0, index=result.index)
        total_weight = sum(self.weights.get(k, 0.0) for k in z_scores)
        if total_weight == 0:
            total_weight = 1.0

        for name, z in z_scores.items():
            w = self.weights.get(name, 0.0)
            composite += z.fillna(0) * w

        composite = composite / total_weight
        result["composite_zscore"] = composite

        # ── Step 5: Rescale to 0-100 ──
        result["composite_score"] = self._to_percentile(composite)

        return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _winsorize_and_zscore(self, series: pd.Series) -> pd.Series:
        """Winsorize then compute z-score. Returns z-scores (mean~0, std~1)."""
        s = series.dropna()
        if len(s) < 10:
            # Not enough data — return neutral z-scores
            return pd.Series(0.0, index=series.index)

        lo, hi = self.winsorize_q
        lower = s.quantile(lo)
        upper = s.quantile(hi)
        clipped = s.clip(lower, upper)

        mean = clipped.mean()
        std = clipped.std(ddof=1)
        if std == 0 or np.isnan(std):
            return pd.Series(0.0, index=series.index)

        z = (series - mean) / std
        return z

    @staticmethod
    def _to_percentile(series: pd.Series) -> pd.Series:
        """Rescale a series to 0-100 using percentile ranks."""
        valid = series.dropna()
        if len(valid) < 10:
            return pd.Series(50.0, index=series.index)
        # Use scipy percentileofscore for consistency
        raw = series.fillna(series.min() if not valid.empty else 0)
        return pd.Series(
            [sp_stats.percentileofscore(raw, x) for x in series],
            index=series.index,
        )


# -----------------------------------------------------------------------
# Default weights and directions
# -----------------------------------------------------------------------

_FACTOR_DIRECTIONS = {
    "momentum_3m": "positive",
    "momentum_12m_1m": "positive",
    "pe_percentile": "negative",
    "pb_percentile": "negative",
    "roe": "positive",
    "roe_stability": "negative",
    "gross_margin": "positive",
    "volatility_60d": "negative",
    "max_drawdown_60d": "negative",
    "avg_turnover_20d": "positive",
}


def _default_weights() -> dict[str, float]:
    return {
        "momentum_3m": 0.15,
        "momentum_12m_1m": 0.10,
        "pe_percentile": 0.15,
        "pb_percentile": 0.10,
        "roe": 0.15,
        "roe_stability": 0.05,
        "gross_margin": 0.10,
        "volatility_60d": 0.05,
        "max_drawdown_60d": 0.05,
        "avg_turnover_20d": 0.10,
    }
