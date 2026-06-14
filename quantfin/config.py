"""Configuration loader: YAML file + environment variable interpolation."""

import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml


_ENV_VAR_RE = re.compile(r"\$\{(\w+)\}")


def _resolve_env(value: Any) -> Any:
    """Recursively resolve ${ENV_VAR} placeholders in config values."""
    if isinstance(value, str):
        def replace(m: re.Match) -> str:
            env_name = m.group(1)
            return os.environ.get(env_name, "")
        return _ENV_VAR_RE.sub(replace, value)
    if isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_env(v) for v in value]
    return value


def load_config(path: Optional[str] = None) -> dict[str, Any]:
    """Load configuration from a YAML file, optionally resolving env vars.

    Args:
        path: Filesystem path to config.yaml. If None, searches in order:
              1. $QUANTFIN_CONFIG
              2. ./config.yaml
              3. ~/.quantfin/config.yaml
    """
    if path is None:
        path = os.environ.get("QUANTFIN_CONFIG",
                               str(Path("config.yaml").resolve()))

    config_path = Path(path)
    if not config_path.exists():
        alt = Path.home() / ".quantfin" / "config.yaml"
        if alt.exists():
            config_path = alt
        else:
            raise FileNotFoundError(
                f"Config not found at {path} or {alt}. "
                "Copy config.yaml.example to config.yaml and edit it."
            )

    with open(config_path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)

    return _resolve_env(raw or {})


def get_default_config() -> dict[str, Any]:
    """Return a minimal default configuration for use when no config file is found."""
    return {
        "notification": {"provider": "none"},
        "factors": {
            "weights": {
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
            },
            "winsorize_quantiles": [0.01, 0.99],
        },
        "timing": {
            "pe_oversold_pct": 30,
            "pe_overbought_pct": 70,
            "pe_extreme_pct": 90,
        },
        "stop_profit": {
            "short_term_return_target": 0.08,
            "medium_term_return_target": 0.15,
            "long_term_return_target": 0.25,
            "score_decline_warning": 0.30,
            "score_decline_exit": 0.50,
        },
        "cache": {
            "dir": "~/.quantfin/cache",
            "ttl_minutes": {
                "spot": 5,
                "hist_daily": 240,
                "financial": 1440,
                "market_valuation": 60,
            },
        },
        "universe": {
            "min_daily_turnover_cny": 10_000_000,
            "min_listing_days": 60,
            "min_etf_aum": 100_000_000,
            "exclude_st": True,
            "max_pe": 200,
        },
    }
