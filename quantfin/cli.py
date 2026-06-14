"""CLI entry point — Click command group for quantfin."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from quantfin import __version__
from quantfin.config import get_default_config, load_config
from quantfin.utils import setup_logger

logger = logging.getLogger(__name__)


def _setup_context(ctx: click.Context, config_path: str | None, verbose: bool):
    """Load config and inject into Click context.obj."""
    level = logging.DEBUG if verbose else logging.INFO
    for name in ("quantfin", "quantfin.data", "quantfin.factors",
                 "quantfin.valuation", "quantfin.signals", "quantfin.notify"):
        setup_logger(name, level)

    setup_logger("quantfin", level)

    try:
        cfg = load_config(config_path)
    except FileNotFoundError:
        logger.warning("No config.yaml found, using defaults (notifications disabled)")
        cfg = get_default_config()

    ctx.ensure_object(dict)
    ctx.obj["config"] = cfg
    ctx.obj["verbose"] = verbose


# ---------------------------------------------------------------------------
# CLI Group
# ---------------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--config", "-c", default=None, help="Path to config.yaml",
              envvar="QUANTFIN_CONFIG")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.version_option(__version__, "--version", "-V")
@click.pass_context
def main(ctx, config, verbose):
    """quantfin — 个人量化理财助手 CLI.

    多因子评分选品 + 估值择时 → 买入/止盈信号 + 微信推送。
    """
    _setup_context(ctx, config, verbose)


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

@main.group()
def scan():
    """扫描市场，生成排名报告。"""


@scan.command("stocks")
@click.option("--top-n", "-n", default=20, help="返回 Top N 只股票")
@click.pass_context
def scan_stocks(ctx, top_n):
    """扫描 A股，输出多因子评分排名。"""
    _run_full_scan(ctx, mode="stocks", top_n=top_n)


@scan.command("etfs")
@click.option("--top-n", "-n", default=10, help="返回 Top N 只 ETF")
@click.pass_context
def scan_etfs(ctx, top_n):
    """扫描 ETF，输出多因子评分排名。"""
    _run_full_scan(ctx, mode="etfs", top_n=top_n)


@scan.command("gold")
@click.pass_context
def scan_gold(ctx):
    """查询黄金现价与近期趋势。"""
    from quantfin.data.fetcher import fetch_gold_spot, fetch_gold_hist

    try:
        price = fetch_gold_spot()
        click.echo(f"黄金期货现价: {price:.1f} CNY/g")

        hist = fetch_gold_hist()
        if not hist.empty and "close" in hist.columns:
            close = hist["close"].dropna()
            if len(close) >= 20:
                mom_20 = (close.iloc[-1] - close.iloc[-20]) / close.iloc[-20] * 100
                click.echo(f"近20日涨跌幅: {mom_20:.1f}%")
                click.echo(f"近5日均价: {close.tail(5).mean():.1f}")
    except Exception as e:
        click.echo(f"获取黄金数据失败: {e}", err=True)


@scan.command("all")
@click.option("--top-n", "-n", default=20, help="返回 Top N 只股票")
@click.pass_context
def scan_all(ctx, top_n):
    """全市场扫描：股票 + ETF + 黄金 + 市场估值。"""
    _run_full_scan(ctx, mode="all", top_n=top_n)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

@main.command()
@click.pass_context
def report(ctx):
    """生成 Markdown 格式的量化日报并输出到 stdout。"""
    result = _run_full_scan(ctx, mode="all", dry_run=True)
    if result:
        print(result)


# ---------------------------------------------------------------------------
# notify
# ---------------------------------------------------------------------------

@main.command()
@click.option("--dry-run", is_flag=True, help="仅生成报告，不发送推送")
@click.pass_context
def notify(ctx, dry_run):
    """扫描市场并推送微信报告 (PushPlus / WxPusher)。"""
    result = _run_full_scan(ctx, mode="all", dry_run=True)
    if result is None:
        click.echo("扫描失败，未生成报告。", err=True)
        return

    if dry_run:
        print(result)
        return

    cfg = ctx.obj.get("config", {})
    notif_cfg = cfg.get("notification", {})
    provider = notif_cfg.get("provider", "none")

    sent = False
    if provider in ("pushplus", "both"):
        pp_cfg = notif_cfg.get("pushplus", {})
        token = pp_cfg.get("token", "")
        if token and "${" not in token:
            from quantfin.notify.pushplus import PushPlusClient
            client = PushPlusClient(token)
            sent = client.send_report(result) or sent
        else:
            logger.warning("PushPlus token not configured (set PUSHPLUS_TOKEN env var)")

    if provider in ("wxpusher", "both"):
        wx_cfg = notif_cfg.get("wxpusher", {})
        app_token = wx_cfg.get("app_token", "")
        uid = wx_cfg.get("uid", "")
        if app_token and uid and "${" not in app_token:
            from quantfin.notify.wxpusher import WxPusherClient
            client = WxPusherClient(app_token, uid)
            sent = client.send_report(result) or sent
        else:
            logger.warning("WxPusher token not configured")

    if not sent and provider not in ("none",):
        click.echo("推送发送失败或无 provider 配置。使用 --dry-run 查看报告内容。", err=True)


# ---------------------------------------------------------------------------
# schedule
# ---------------------------------------------------------------------------

@main.command()
@click.pass_context
def schedule(ctx):
    """输出建议的 crontab 配置行。"""
    import os
    cwd = os.getcwd()
    python = sys.executable
    config_arg = ""
    if ctx.obj.get("config_path"):
        config_arg = f" --config {ctx.obj['config_path']}"

    lines = [
        "# quantfin 定时任务配置",
        "# 每天收盘后 (18:00) 运行扫描并推送",
        f"0 18 * * 1-5 cd {cwd} && {python} -m quantfin notify{config_arg}",
        "",
        "# 或每小时运行 (盘中监控)",
        f"# */60 * * * 1-5 cd {cwd} && {python} -m quantfin notify{config_arg}",
        "",
        "# Windows 计划任务 (schtasks):",
        '# schtasks /create /tn quantfin /tr "python -m quantfin notify" /sc daily /st 18:00',
    ]
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Internal: unified scan pipeline
# ---------------------------------------------------------------------------

def _run_full_scan(
    ctx: click.Context,
    mode: str = "all",        # "stocks" | "etfs" | "all"
    top_n: int = 20,
    dry_run: bool = False,
) -> str | None:
    """Run the complete scan → score → rank → format pipeline.

    Returns the Markdown report string, or None on failure.
    """
    cfg = ctx.obj.get("config", {})
    from datetime import datetime

    from quantfin.data.cache import DataCache
    from quantfin.data.universe import UniverseBuilder
    from quantfin.factors import liquidity, momentum, quality, value, volatility
    from quantfin.factors.engine import FactorEngine
    from quantfin.notify.formatter import ReportFormatter
    from quantfin.signals.ranking import RankingEngine
    from quantfin.valuation.market_wide import MarketValuation

    # ── Setup ──
    cache_cfg = cfg.get("cache", {})
    cache_dir = Path(cache_cfg.get("dir", "~/.quantfin/cache")).expanduser()
    cache = DataCache(cache_dir)

    universe_builder = UniverseBuilder(cfg, cache)
    factor_engine = FactorEngine(cfg.get("factors"))
    ranking_engine = RankingEngine(cfg)
    market_val = MarketValuation(cfg, cache)
    formatter = ReportFormatter()

    # ── Market Snapshot ──
    market_snap = market_val.get_snapshot()
    if ctx.obj.get("verbose"):
        logger.info("Market: %s (PE %.0f%%, PB %.0f%%)",
                    market_snap.signal.value, market_snap.pe_percentile, market_snap.pb_percentile)

    gold_price = None
    top_stocks = None
    top_etfs = None

    # ── Gold ──
    if mode in ("all", "gold"):
        try:
            from quantfin.data.fetcher import fetch_gold_spot
            gold_price = fetch_gold_spot()
        except Exception:
            logger.warning("Failed to fetch gold price")

    # ── Stock Scan ──
    if mode in ("stocks", "all"):
        try:
            universe = universe_builder.build_stock_universe()
            if universe.empty:
                logger.warning("Stock universe is empty")
            else:
                # Compute factor values cross-sectionally
                factor_data = _compute_stock_factors(universe, cache)
                scored = factor_engine.score(universe, factor_data)
                top_stocks = ranking_engine.rank_stocks(
                    scored,
                    pe_pct_col="pe_percentile_raw",
                    pb_pct_col="pb_percentile_raw",
                    market_signal=market_snap.signal,
                    top_n=top_n,
                )
                if not dry_run:
                    _print_stock_table(top_stocks)
        except Exception:
            logger.error("Stock scan failed", exc_info=True)
            if ctx.obj.get("verbose"):
                import traceback
                traceback.print_exc()

    # ── ETF Scan ──
    if mode in ("etfs", "all"):
        try:
            etf_universe = universe_builder.build_etf_universe()
            if etf_universe.empty:
                logger.warning("ETF universe is empty")
            else:
                etf_factor_data = _compute_etf_factors(etf_universe, cache)
                etf_scored = factor_engine.score(etf_universe, etf_factor_data)
                top_etfs = ranking_engine.rank_etfs(
                    etf_scored, market_signal=market_snap.signal, top_n=top_n // 2,
                )
                if not dry_run:
                    _print_etf_table(top_etfs)
        except Exception:
            logger.error("ETF scan failed", exc_info=True)

    # ── Format Report ──
    report = formatter.format_full_report(
        top_stocks=top_stocks,
        top_etfs=top_etfs,
        market_snap=market_snap,
        gold_price=gold_price,
        timestamp=datetime.now(),
    )
    return report


# ---------------------------------------------------------------------------
# Factor computation helpers
# ---------------------------------------------------------------------------

def _compute_stock_factors(universe: pd.DataFrame, cache: DataCache) -> dict:
    """Compute factor raw values for the stock universe."""
    from quantfin.data.fetcher import fetch_a_share_hist, fetch_hist_batch

    factors: dict[str, list] = {
        "momentum_3m": [], "momentum_12m_1m": [],
        "pe_percentile": [], "pb_percentile": [],
        "roe": [], "roe_stability": [], "gross_margin": [],
        "volatility_60d": [], "max_drawdown_60d": [],
        "avg_turnover_20d": [],
    }

    # PE/PB percentile cross-sectionally (fast path)
    for _, row in universe.iterrows():
        factors["pe_percentile"].append(
            value.pe_percentile_from_spot(row, universe))
        factors["pb_percentile"].append(
            value.pb_percentile_from_spot(row, universe))
        factors["avg_turnover_20d"].append(
            liquidity.avg_turnover_rate(row))
        factors["roe"].append(0.0)
        factors["roe_stability"].append(50.0)
        factors["gross_margin"].append(0.0)

    # Fetch history for top stocks by market cap (limit for speed)
    top_symbols = universe.sort_values("total_mcap", ascending=False).head(100)["symbol"].tolist() if "total_mcap" in universe.columns else universe["symbol"].head(50).tolist()

    hist_map = fetch_hist_batch(top_symbols, "stock", start_date="20210101")

    idx = 0
    for _, row in universe.iterrows():
        sym = row.get("symbol", "")
        df = hist_map.get(sym)
        if df is not None and len(df) >= 60:
            factors["momentum_3m"][idx] = momentum.momentum_3m(df)
            factors["momentum_12m_1m"][idx] = momentum.momentum_12m_1m(df)
            factors["volatility_60d"][idx] = volatility.volatility_60d(df) or 0.0
            factors["max_drawdown_60d"][idx] = volatility.max_drawdown_60d(df) or 0.0
        else:
            factors["momentum_3m"][idx] = 0.0
            factors["momentum_12m_1m"][idx] = 0.0
            factors["volatility_60d"][idx] = 0.0
            factors["max_drawdown_60d"][idx] = 0.0

        # Financials (only for top 50)
        if idx < 50:
            try:
                fin_df = cache.fetch_or_cache(
                    f"financial/{sym}",
                    lambda s=sym: __import__("quantfin.data.fetcher", fromlist=["fetch_financial_indicator"]).fetch_financial_indicator(s),
                )
                if fin_df is not None and not fin_df.empty:
                    factors["roe"][idx] = quality.compute_roe(fin_df)
                    factors["roe_stability"][idx] = quality.compute_roe_stability(fin_df)
                    factors["gross_margin"][idx] = quality.compute_gross_margin(fin_df)
            except Exception:
                pass
        idx += 1

    return {k: __import__("pandas").Series(v) for k, v in factors.items()}


def _compute_etf_factors(universe: pd.DataFrame, cache: DataCache) -> dict:
    """Compute factor raw values for the ETF universe (simplified)."""
    import pandas as pd
    from quantfin.data.fetcher import fetch_etf_hist

    factors = {
        "momentum_3m": [], "momentum_12m_1m": [],
        "pe_percentile": [], "pb_percentile": [],
        "roe": [], "roe_stability": [], "gross_margin": [],
        "volatility_60d": [], "max_drawdown_60d": [],
        "avg_turnover_20d": [],
    }

    for _, row in universe.iterrows():
        sym = row.get("symbol", "")
        try:
            df = cache.fetch_or_cache(
                f"hist_daily/etf_{sym}",
                lambda s=sym: fetch_etf_hist(s, start_date="20210101"),
            )
            factors["momentum_3m"].append(momentum.momentum_3m(df) if not df.empty else 0.0)
            factors["momentum_12m_1m"].append(momentum.momentum_12m_1m(df) if not df.empty else 0.0)
            factors["volatility_60d"].append(volatility.volatility_60d(df) or 0.0 if not df.empty else 0.0)
            factors["max_drawdown_60d"].append(volatility.max_drawdown_60d(df) or 0.0 if not df.empty else 0.0)
        except Exception:
            factors["momentum_3m"].append(0.0)
            factors["momentum_12m_1m"].append(0.0)
            factors["volatility_60d"].append(0.0)
            factors["max_drawdown_60d"].append(0.0)

        factors["pe_percentile"].append(50.0)
        factors["pb_percentile"].append(50.0)
        factors["roe"].append(0.0)
        factors["roe_stability"].append(50.0)
        factors["gross_margin"].append(0.0)
        factors["avg_turnover_20d"].append(row.get("turnover_rate", 0.0) or 0.0)

    return {k: pd.Series(v) for k, v in factors.items()}


# ---------------------------------------------------------------------------
# Table output helpers
# ---------------------------------------------------------------------------

def _print_stock_table(df):
    """Pretty-print a stock ranking table with rich formatting."""
    if df is None or df.empty:
        click.echo("暂无符合条件的股票。")
        return

    click.echo()
    click.secho(f"===== A股优选 Top {len(df)} =====", fg="cyan", bold=True)

    for _, row in df.iterrows():
        rank = int(row.get("rank", 0))
        score = row.get("composite_score", 0)
        signal = row.get("buy_signal", "")
        name = row.get("name", "")
        sym = row.get("symbol", "")

        # Color by signal
        color = "green" if "BUY" in str(signal) else ("yellow" if "WATCH" in str(signal) else "white")
        click.echo(
            f"  #{rank:<3} "
            f"{click.style(f'{score:5.1f}', fg=color, bold=True)}  "
            f"{sym} {name:<10s} "
            f"{click.style(str(signal), fg=color)}"
        )


def _print_etf_table(df):
    """Pretty-print an ETF ranking table."""
    if df is None or df.empty:
        click.echo("暂无符合条件的ETF。")
        return

    click.echo()
    click.secho(f"===== ETF优选 Top {len(df)} =====", fg="green", bold=True)

    for _, row in df.iterrows():
        rank = int(row.get("rank", 0))
        score = row.get("composite_score", 0)
        name = row.get("name", "")
        sym = row.get("symbol", "")
        click.echo(f"  #{rank:<3} {score:5.1f}  {sym} {name}")
