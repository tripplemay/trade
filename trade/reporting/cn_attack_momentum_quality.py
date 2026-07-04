"""B066 F003 — CN attack multi-variant comparison report (research judgment).

Runs the 2 factor variants × 3 exit variants = **6 configurations** over the same
window, splits each into a walk-forward in-sample (design) / out-of-sample
(validation) segment, compares all six against the CSI 300 (沪深300) benchmark, and
raises **over-fitting red flags** — the whole point of the P1 research judgment:
which variant is best *out of sample*, does quality add value, which exit rule
wins, and is any result too good to be true.

Discipline (spec §1 / §5): **all six variants are disclosed**, never just the
in-sample winner; the in-sample-best-vs-out-of-sample-best divergence, implausibly
high Sharpe, and indistinguishable-variants cases are flagged so a reader does not
over-trust a data-snooped number.

Pure ``trade`` (no akshare / broker); reuses the F002 engine + the shared metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.backtest.cn_attack_momentum_quality.engine import (
    DEFAULT_WARMUP_MONTHS,
    EXIT_HARD_PROFIT_TARGET,
    EXIT_MOMENTUM_DECAY,
    EXIT_TRAILING_STOP,
    CnAttackBacktestConfig,
    CnAttackBacktestResult,
    run_cn_attack_backtest,
)
from trade.backtest.us_quality_momentum.metrics import (
    annualized_return,
    max_drawdown,
    sharpe_ratio,
)
from trade.data.cn_benchmark import load_cn_benchmark
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    CnAttackParameters,
)

# The 6-cell grid: 2 factor variants × 3 exit variants (spec §1 A/B + exit compare).
_FACTOR_VARIANTS = (FACTOR_VARIANT_QUALITY_MOMENTUM, FACTOR_VARIANT_PURE_MOMENTUM)
_EXIT_VARIANTS = (EXIT_MOMENTUM_DECAY, EXIT_TRAILING_STOP, EXIT_HARD_PROFIT_TARGET)

# The headline variant shown on the chart (the comparison lives in the markdown):
# the quality+momentum blend with the let-winners-run base exit.
_HEADLINE_FACTOR = FACTOR_VARIANT_QUALITY_MOMENTUM
_HEADLINE_EXIT = EXIT_MOMENTUM_DECAY

_IN_SAMPLE_FRACTION = 0.7  # walk-forward split: first 70% design, last 30% validation
_IMPLAUSIBLE_SHARPE = 3.0  # a daily-rebalanced A-share Sharpe above this is suspect
_INDISTINGUISHABLE_CAGR_SPREAD = 0.01  # variants within 1% CAGR ⇒ factor/exit moot


@dataclass(frozen=True, slots=True)
class VariantMetrics:
    """Full-sample + walk-forward metrics for one (factor, exit) configuration."""

    factor_variant: str
    exit_variant: str
    cagr: float
    sharpe: float
    max_drawdown: float
    turnover: float
    total_cost: float
    rebalance_count: int
    exit_count: int
    in_sample_cagr: float
    in_sample_sharpe: float
    out_sample_cagr: float
    out_sample_sharpe: float


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    """CSI 300 benchmark metrics over the same window (or unavailable)."""

    available: bool
    cagr: float
    sharpe: float
    max_drawdown: float


@dataclass(frozen=True, slots=True)
class CnAttackComparison:
    """All six variants + walk-forward + benchmark + over-fitting flags."""

    start: date
    end: date
    in_sample_end: date | None
    variants: tuple[VariantMetrics, ...]
    benchmark: BenchmarkMetrics
    overfitting_flags: tuple[str, ...]
    headline: CnAttackBacktestResult
    headline_label: str


def _equity_segment(equity_curve: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp) -> pd.DataFrame:
    seg = equity_curve[(equity_curve["date"] >= lo) & (equity_curve["date"] <= hi)]
    return seg.reset_index(drop=True)


def _segment_cagr_sharpe(segment: pd.DataFrame) -> tuple[float, float]:
    if len(segment) < 2:
        return 0.0, 0.0
    returns = segment.set_index("date")["equity"].pct_change().dropna()
    return annualized_return(segment), sharpe_ratio(returns)


def _split_date(equity_curve: pd.DataFrame) -> pd.Timestamp | None:
    if len(equity_curve) < 4:
        return None
    dates = equity_curve["date"].tolist()
    idx = max(1, min(len(dates) - 2, int(len(dates) * _IN_SAMPLE_FRACTION)))
    return pd.Timestamp(dates[idx])


def _variant_metrics(
    result: CnAttackBacktestResult, split: pd.Timestamp | None
) -> VariantMetrics:
    curve = result.equity_curve
    if split is None:
        in_cagr, in_sharpe = result.metrics.annualized_return, result.metrics.sharpe_ratio
        out_cagr, out_sharpe = 0.0, 0.0
    else:
        first = pd.Timestamp(curve["date"].iloc[0])
        last = pd.Timestamp(curve["date"].iloc[-1])
        in_cagr, in_sharpe = _segment_cagr_sharpe(_equity_segment(curve, first, split))
        out_cagr, out_sharpe = _segment_cagr_sharpe(_equity_segment(curve, split, last))
    return VariantMetrics(
        factor_variant=result.parameters.factor_variant,
        exit_variant=result.config.exit_variant,
        cagr=result.metrics.annualized_return,
        sharpe=result.metrics.sharpe_ratio,
        max_drawdown=result.metrics.max_drawdown,
        turnover=result.total_turnover,
        total_cost=result.total_cost,
        rebalance_count=result.rebalance_count,
        exit_count=result.exit_count,
        in_sample_cagr=in_cagr,
        in_sample_sharpe=in_sharpe,
        out_sample_cagr=out_cagr,
        out_sample_sharpe=out_sharpe,
    )


def _benchmark_metrics(
    benchmark: pd.Series, lo: pd.Timestamp, hi: pd.Timestamp
) -> BenchmarkMetrics:
    if benchmark.empty:
        return BenchmarkMetrics(available=False, cagr=0.0, sharpe=0.0, max_drawdown=0.0)
    windowed = benchmark[(benchmark.index >= lo) & (benchmark.index <= hi)]
    if len(windowed) < 2:
        return BenchmarkMetrics(available=False, cagr=0.0, sharpe=0.0, max_drawdown=0.0)
    curve = pd.DataFrame({"date": windowed.index, "equity": windowed.to_numpy()})
    returns = curve.set_index("date")["equity"].pct_change().dropna()
    return BenchmarkMetrics(
        available=True,
        cagr=annualized_return(curve),
        sharpe=sharpe_ratio(returns),
        max_drawdown=max_drawdown(curve),
    )


def _variant_label(metrics: VariantMetrics) -> str:
    return f"{metrics.factor_variant}+{metrics.exit_variant}"


def _overfitting_flags(
    variants: tuple[VariantMetrics, ...],
    has_out_sample: bool,
    headline_label: str,
) -> tuple[str, ...]:
    flags: list[str] = []
    if has_out_sample and len(variants) > 1:
        in_best = max(variants, key=lambda v: v.in_sample_sharpe)
        out_best = max(variants, key=lambda v: v.out_sample_sharpe)
        if _variant_label(in_best) != _variant_label(out_best):
            flags.append(
                "in_sample_winner_not_out_of_sample: "
                f"in-sample best ({_variant_label(in_best)}) ≠ out-of-sample best "
                f"({_variant_label(out_best)}) — do NOT cherry-pick the in-sample winner"
            )
    implausible = [v for v in variants if v.sharpe > _IMPLAUSIBLE_SHARPE]
    if implausible:
        flags.append(
            "implausible_sharpe: "
            + ", ".join(f"{_variant_label(v)} Sharpe={v.sharpe:.2f}" for v in implausible)
            + f" (> {_IMPLAUSIBLE_SHARPE}) — suspect, likely over-fit / too short a sample"
        )
    # Degenerate / no-activity: a variant that never rebalanced (empty cross-section
    # — e.g. quality names dropped out because CAS fundamentals were thin/absent for
    # the PIT universe) reports a clean 0.00% that is NOT a real result. Loud when it
    # is the headline, since the headline drives the chart + payload metrics.
    inert = [v for v in variants if v.rebalance_count == 0]
    if inert:
        labels = ", ".join(_variant_label(v) for v in inert)
        headline_inert = any(_variant_label(v) == headline_label for v in inert)
        suffix = " [INCLUDES HEADLINE — chart & metrics unreliable]" if headline_inert else ""
        flags.append(
            f"no_activity: {labels} never traded (empty cross-section / missing factor "
            f"data) — its 0.00% is NOT a real result{suffix}"
        )
    cagrs = [v.cagr for v in variants]
    if cagrs and (max(cagrs) - min(cagrs)) < _INDISTINGUISHABLE_CAGR_SPREAD:
        flags.append(
            f"indistinguishable_variants: all {len(variants)} variants within "
            f"{_INDISTINGUISHABLE_CAGR_SPREAD:.0%} CAGR — neither the quality factor "
            "nor the exit rule meaningfully differentiates on this sample"
        )
    # Within a factor family, identical (CAGR, Sharpe) across the 3 exit variants
    # means the exit overlay provably never engaged — the most common inert-toggle
    # over-fitting symptom, invisible to the global spread test when factor families
    # diverge (one family flat, the other not).
    for factor in sorted({v.factor_variant for v in variants}):
        family = [v for v in variants if v.factor_variant == factor]
        signatures = {(round(v.cagr, 6), round(v.sharpe, 6)) for v in family}
        if len(family) > 1 and len(signatures) == 1:
            flags.append(
                f"exit_overlay_inert: the {len(family)} exit variants for factor "
                f"'{factor}' are identical — the exit rule never engaged on this sample"
            )
    return tuple(flags)


def build_cn_attack_comparison(
    start: date,
    end: date,
    *,
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame | None,
    universe_history: dict[date, tuple[str, ...]],
    benchmark: pd.Series | None = None,
    config: CnAttackBacktestConfig | None = None,
) -> CnAttackComparison:
    """Run the 6-variant grid, split walk-forward, compare vs CSI 300, flag over-fit.

    ``config`` supplies the non-variant knobs (capital, band, exit thresholds, cost
    model); the factor + exit variants are swept here. ``benchmark`` defaults to the
    on-disk CSI 300 series (empty ⇒ benchmark unavailable, reported honestly).
    """

    base = config or CnAttackBacktestConfig()
    if benchmark is None:
        benchmark = load_cn_benchmark(start, end)

    results: list[CnAttackBacktestResult] = []
    headline: CnAttackBacktestResult | None = None
    for factor in _FACTOR_VARIANTS:
        params = CnAttackParameters(factor_variant=factor)
        for exit_variant in _EXIT_VARIANTS:
            cfg = CnAttackBacktestConfig(
                starting_capital=base.starting_capital,
                cost_model=base.cost_model,
                no_trade_band=base.no_trade_band,
                exit_variant=exit_variant,
                trailing_stop_pct=base.trailing_stop_pct,
                profit_target_pct=base.profit_target_pct,
                # B081 F001 — honor the base config's engine-fidelity switches across
                # every variant (previously dropped → the comparison always ran the
                # new default口径, ignoring a caller's lot_rounding=False).
                lot_rounding=base.lot_rounding,
            )
            result = run_cn_attack_backtest(
                params,
                cfg,
                start,
                end,
                prices=prices,
                fundamentals=fundamentals,
                universe_history=universe_history,
            )
            results.append(result)
            if factor == _HEADLINE_FACTOR and exit_variant == _HEADLINE_EXIT:
                headline = result

    if headline is None:  # defensive — the headline cell is always in the grid
        headline = results[0]

    split = _split_date(headline.equity_curve)
    variants = tuple(_variant_metrics(result, split) for result in results)
    lo = pd.Timestamp(headline.equity_curve["date"].iloc[0])
    hi = pd.Timestamp(headline.equity_curve["date"].iloc[-1])
    benchmark_metrics = _benchmark_metrics(benchmark, lo, hi)
    headline_label = f"{_HEADLINE_FACTOR}+{_HEADLINE_EXIT}"
    flags = _overfitting_flags(
        variants, has_out_sample=split is not None, headline_label=headline_label
    )

    return CnAttackComparison(
        start=start,
        end=end,
        in_sample_end=split.date() if split is not None else None,
        variants=variants,
        benchmark=benchmark_metrics,
        overfitting_flags=flags,
        headline=headline,
        headline_label=f"{_HEADLINE_FACTOR}+{_HEADLINE_EXIT}",
    )


def run_cn_attack_comparison(
    start: date | None = None,
    end: date | None = None,
    *,
    config: CnAttackBacktestConfig | None = None,
) -> CnAttackComparison:
    """Load the unified CN data from disk and run the 6-variant comparison.

    The worker calls this (it imports ``trade`` off the request path). ``start`` /
    ``end`` default to the engine's warmed window (data start + ~14 months → data
    end). The benchmark, universe history, prices and fundamentals all load from
    the VM data root (``WORKBENCH_DATA_ROOT``); an absent benchmark degrades.
    """

    from trade.data.cn_attack_universe import load_cn_universe_history
    from trade.data.us_quality_universe import load_fundamentals, load_prices

    prices = load_prices()
    if prices.empty:
        raise ValueError("no price data available for the CN attack comparison")
    if start is None:
        start = (
            pd.Timestamp(prices["date"].min()) + pd.DateOffset(months=DEFAULT_WARMUP_MONTHS)
        ).date()
    if end is None:
        end = pd.Timestamp(prices["date"].max()).date()
    return build_cn_attack_comparison(
        start,
        end,
        prices=prices,
        fundamentals=load_fundamentals(),
        universe_history=load_cn_universe_history(),
        benchmark=load_cn_benchmark(start, end),
        config=config,
    )


def _headline_variant(comparison: CnAttackComparison) -> VariantMetrics:
    for variant in comparison.variants:
        if _variant_label(variant) == comparison.headline_label:
            return variant
    return comparison.variants[0]


def build_cn_attack_report_payload(
    comparison: CnAttackComparison, run_id: str
) -> dict[str, object]:
    """JSON payload: ``metrics`` (headline, read by ``map_metrics``) + the full
    6-variant comparison / walk-forward / benchmark / over-fitting flags."""

    headline = _headline_variant(comparison)
    return {
        "run": {"run_id": run_id, "strategy_id": "cn_attack_momentum_quality"},
        "window": {
            "start": comparison.start.isoformat(),
            "end": comparison.end.isoformat(),
            "in_sample_end": (
                comparison.in_sample_end.isoformat() if comparison.in_sample_end else None
            ),
        },
        "metrics": {
            "CAGR": headline.cagr,
            "Sharpe": headline.sharpe,
            "max_drawdown": headline.max_drawdown,
            "turnover": headline.turnover,
            "transaction_costs": headline.total_cost,
        },
        "headline_variant": comparison.headline_label,
        "variants": [
            {
                "factor_variant": v.factor_variant,
                "exit_variant": v.exit_variant,
                "CAGR": v.cagr,
                "Sharpe": v.sharpe,
                "max_drawdown": v.max_drawdown,
                "turnover": v.turnover,
                "transaction_costs": v.total_cost,
                "rebalance_count": v.rebalance_count,
                "exit_count": v.exit_count,
                "in_sample_CAGR": v.in_sample_cagr,
                "in_sample_Sharpe": v.in_sample_sharpe,
                "out_sample_CAGR": v.out_sample_cagr,
                "out_sample_Sharpe": v.out_sample_sharpe,
            }
            for v in comparison.variants
        ],
        "benchmark": {
            "name": "沪深300 (CSI 300)",
            "available": comparison.benchmark.available,
            "CAGR": comparison.benchmark.cagr,
            "Sharpe": comparison.benchmark.sharpe,
            "max_drawdown": comparison.benchmark.max_drawdown,
        },
        "overfitting_flags": list(comparison.overfitting_flags),
        "research_only": True,
    }


def _pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def render_cn_attack_markdown(comparison: CnAttackComparison) -> str:
    """Bilingual research report: 6-variant table + walk-forward + 沪深300 + 红旗."""

    lines: list[str] = [
        "# A股 进攻动量质量 多变体对比报告（研究态 research-only）",
        "",
        f"- 回测区间 / Window: {comparison.start.isoformat()} → {comparison.end.isoformat()}",
        "- 样本内/外切分 / In-sample split: "
        + (comparison.in_sample_end.isoformat() if comparison.in_sample_end else "n/a"),
        f"- Headline 变体（图表展示）: {comparison.headline_label}",
        "",
        "> 研究纪律：6 变体**全部披露**，不 cherry-pick 样本内赢家；以**样本外**表现为准。",
        "",
        "## 全样本对比 / Full-sample comparison",
        "",
        "| 因子 Factor | 退出 Exit | CAGR | Sharpe | MaxDD | 换手 | 成本 | 调仓 | 退出日 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for v in comparison.variants:
        lines.append(
            f"| {v.factor_variant} | {v.exit_variant} | {_pct(v.cagr)} | {v.sharpe:.2f} | "
            f"{_pct(v.max_drawdown)} | {v.turnover:.2f} | {v.total_cost:.0f} | "
            f"{v.rebalance_count} | {v.exit_count} |"
        )
    lines += [
        "",
        "## Walk-forward 样本外验证 / Out-of-sample validation",
        "",
        "| 因子 Factor | 退出 Exit | 样本内 CAGR | 样本内 Sharpe | 样本外 CAGR | 样本外 Sharpe |",
        "|---|---|---|---|---|---|",
    ]
    for v in comparison.variants:
        lines.append(
            f"| {v.factor_variant} | {v.exit_variant} | {_pct(v.in_sample_cagr)} | "
            f"{v.in_sample_sharpe:.2f} | {_pct(v.out_sample_cagr)} | {v.out_sample_sharpe:.2f} |"
        )
    lines += ["", "## 基准 / Benchmark — 沪深300 (CSI 300)", ""]
    if comparison.benchmark.available:
        lines.append(
            f"- CAGR {_pct(comparison.benchmark.cagr)} / Sharpe "
            f"{comparison.benchmark.sharpe:.2f} / MaxDD {_pct(comparison.benchmark.max_drawdown)}"
        )
    else:
        lines.append("- ⚠️ 基准数据不可用 / benchmark unavailable（沪深300 指数 CSV 缺失）。")
    lines += ["", "## 过拟合红旗 / Over-fitting red flags", ""]
    if comparison.overfitting_flags:
        lines += [f"- 🚩 {flag}" for flag in comparison.overfitting_flags]
    else:
        lines.append("- 无显著红旗（仍以样本外为准，区间短则谨慎）/ none flagged.")
    lines += [
        "",
        "## 研究判定指引 / Research verdict",
        "",
        "- 据**样本外**最优变体 + 质量是否加值 + 哪种退出好，判断是否值得进 P2 实盘 advisory。",
        "- research-only：无实盘推荐 / 无执行 / 无收益预测 / 不碰 live。",
    ]
    return "\n".join(lines)


__all__ = [
    "BenchmarkMetrics",
    "CnAttackComparison",
    "VariantMetrics",
    "build_cn_attack_comparison",
    "build_cn_attack_report_payload",
    "render_cn_attack_markdown",
    "run_cn_attack_comparison",
]
