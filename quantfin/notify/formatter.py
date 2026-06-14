"""Report formatter: DataFrame → Markdown report string."""

from __future__ import annotations

from datetime import datetime

import pandas as pd

from quantfin.valuation.market_wide import MarketSignal, MarketSnapshot


class ReportFormatter:
    """Format ranked results into a readable Markdown daily report."""

    @staticmethod
    def format_full_report(
        top_stocks: pd.DataFrame,
        top_etfs: pd.DataFrame | None = None,
        market_snap: MarketSnapshot | None = None,
        gold_price: float | None = None,
        timestamp: datetime | None = None,
    ) -> str:
        """Generate the complete markdown daily report.

        Args:
            top_stocks: Ranked stock DataFrame from RankingEngine.rank_stocks().
            top_etfs: Ranked ETF DataFrame from RankingEngine.rank_etfs().
            market_snap: Market valuation snapshot.
            gold_price: Current gold AU2502 price (CNY/g).
            timestamp: Report timestamp.

        Returns full markdown report string.
        """
        ts = timestamp or datetime.now()
        lines = [
            f"## 量化分析日报 - {ts.strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        # ── Market Valuation ──
        if market_snap:
            lines.append("### 市场估值温度")
            lines.append("")
            lines.append("| 指标 | 数值 | 百分位 | 状态 |")
            lines.append("|------|------|--------|------|")
            lines.append(
                f"| A股PE中位数 | {market_snap.pe_median:.1f} | "
                f"{market_snap.pe_percentile:.0f}% | "
                f"{_signal_emoji(market_snap.signal)} {market_snap.signal.value} |"
            )
            lines.append(
                f"| A股PB中位数 | {market_snap.pb_median:.2f} | "
                f"{market_snap.pb_percentile:.0f}% | — |"
            )
            lines.append(
                f"| 10Y国债收益率 | {market_snap.bond_yield_10y:.2f}% | — | — |"
            )
            spread_label = "合理" if abs(market_snap.yield_spread) < 3 else "极端"
            lines.append(
                f"| 股债利差 | {market_snap.yield_spread:.2f}% | — | {spread_label} |"
            )
            if gold_price:
                lines.append(f"| 黄金(期货) | {gold_price:.1f} CNY/g | — | — |")
            lines.append("")

        # ── Stock Rankings ──
        if top_stocks is not None and not top_stocks.empty:
            lines.append(f"### 股票优选 Top {len(top_stocks)}")
            lines.append("")
            # Header
            cols = _select_columns(top_stocks, {
                "rank": "排名", "symbol": "代码", "name": "名称",
                "composite_score": "综合评分", "pe_pct": "PE分位",
                "pb_pct": "PB分位", "timing": "择时", "buy_signal": "买入信号",
                "holding": "建议持有",
            })
            header, col_keys = _build_header(cols)
            lines.append(header)
            lines.append(_build_sep(len(col_keys)))

            for _, row in top_stocks.iterrows():
                vals = []
                for k in col_keys:
                    v = row.get(k, "")
                    if "score" in k:
                        vals.append(f"{v:.1f}")
                    elif "pct" in k:
                        vals.append(f"{v:.0f}%")
                    elif k == "buy_signal":
                        vals.append(_buy_emoji(str(v)))
                    else:
                        vals.append(f"{v}")
                lines.append("| " + " | ".join(vals) + " |")
            lines.append("")

        # ── ETF Rankings ──
        if top_etfs is not None and not top_etfs.empty:
            lines.append(f"### ETF优选 Top {len(top_etfs)}")
            lines.append("")
            cols = _select_columns(top_etfs, {
                "rank": "排名", "symbol": "代码", "name": "名称",
                "composite_score": "综合评分", "price": "价格",
                "pct_change": "涨跌", "holding": "建议持有",
            })
            header, col_keys = _build_header(cols)
            lines.append(header)
            lines.append(_build_sep(len(col_keys)))

            for _, row in top_etfs.iterrows():
                vals = []
                for k in col_keys:
                    v = row.get(k, "")
                    if "score" in k:
                        vals.append(f"{v:.1f}")
                    elif "pct_change" in k:
                        vals.append(f"{v:.2f}%")
                    else:
                        vals.append(f"{v}")
                lines.append("| " + " | ".join(vals) + " |")
            lines.append("")

        # ── Summary ──
        if top_stocks is not None and not top_stocks.empty:
            n_buy = 0
            if "buy_signal" in top_stocks.columns:
                n_buy = int((top_stocks["buy_signal"].isin(["STRONG_BUY", "BUY"])).sum())
            lines.append("### 信号概览")
            lines.append(f"- **强买/买入**: {n_buy} 只")
            if market_snap:
                position_pct = _suggested_position(market_snap.signal)
                lines.append(f"- **建议仓位**: {position_pct}% ({market_snap.signal.value})")
            lines.append("")
            lines.append("> ⚠️ 以上信号仅供研究参考，不构成投资建议。投资有风险，入市需谨慎。")

        return "\n".join(lines)


# -----------------------------------------------------------------------
# Internal helpers
# -----------------------------------------------------------------------

def _select_columns(df: pd.DataFrame, mapping: dict[str, str]) -> dict[str, str]:
    """Return subset of mapping that exists in df columns."""
    return {k: v for k, v in mapping.items() if k in df.columns}


def _build_header(cols: dict[str, str]) -> tuple[str, list[str]]:
    """Build markdown table header and return keys."""
    keys = list(cols.keys())
    names = [cols[k] for k in keys]
    return "| " + " | ".join(names) + " |", keys


def _build_sep(n: int) -> str:
    return "|" + "|".join(["------"] * n) + "|"


def _signal_emoji(signal: MarketSignal) -> str:
    mapping = {
        MarketSignal.OVERSOLD: "🟢",
        MarketSignal.UNDERVALUED: "🟢",
        MarketSignal.NEUTRAL: "🟡",
        MarketSignal.OVERVALUED: "🟠",
        MarketSignal.OVERBOUGHT: "🔴",
    }
    return mapping.get(signal, "⚪")


def _buy_emoji(signal: str) -> str:
    mapping = {
        "STRONG_BUY": "🔥 强买",
        "BUY": "✅ 买入",
        "WATCH": "👀 关注",
        "NO_SIGNAL": "—",
    }
    return mapping.get(signal, signal)


def _suggested_position(signal: MarketSignal) -> int:
    mapping = {
        MarketSignal.OVERSOLD: 90,
        MarketSignal.UNDERVALUED: 75,
        MarketSignal.NEUTRAL: 50,
        MarketSignal.OVERVALUED: 25,
        MarketSignal.OVERBOUGHT: 10,
    }
    return mapping.get(signal, 50)
