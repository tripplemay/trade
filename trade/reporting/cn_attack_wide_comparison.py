"""B068 F003 — CN attack WIDE-universe weighting comparison (research judgment).

Runs the spec's **4-cell grid** — 2 factor variants × 2 weighting schemes, exit
FIXED to ``momentum_decay`` (the data-snooping discipline: only the weighting
dimension is added on top of B066's exit study, never a 3× variant explosion) —
over the **wide** point-in-time universe (F001: top-250 PIT, vs B066's seed-43),
splits each into walk-forward in-sample/out-of-sample segments, compares against
the CSI 300 (沪深300), raises over-fitting red flags, and **answers the three
B066-open questions**:

* **Q1** — does *quality* add value? (quality+momentum vs pure-momentum, now that
  a 250-name universe gives the quality filter real selection power that seed-43
  could not — every seed name passed the gate).
* **Q2** — does *inverse-vol* weighting tame the OOS momentum crash? (equal vs
  1/σ — risk-managed momentum, Barroso-Santa-Clara / Daniel-Moskowitz).
* **Q3** — is the wider / longer OOS still fragile? (B066's OOS was a single
  2025H2 momentum reversal, −9~−11%).

This is a SEPARATE module from :mod:`trade.reporting.cn_attack_momentum_quality`
(B066's 6-exit comparison, which is wired into the production backtest worker and
must stay byte-identical — spec invariant #1). It reuses the shared engine +
metrics primitives; the small walk-forward / benchmark helpers are intentionally
mirrored (not imported from B066's private API) so this research module is
self-contained and B066 is never coupled to it.

Discipline (spec §2): **all four configs disclosed**, never the in-sample winner;
the verdicts are data-driven from the OUT-OF-SAMPLE segment with honest
short-sample caveats. Pure ``trade`` (no akshare / broker).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.backtest.cn_attack_momentum_quality.engine import (
    DEFAULT_WARMUP_MONTHS,
    EXIT_MOMENTUM_DECAY,
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
    WEIGHTING_SCHEME_EQUAL,
    WEIGHTING_SCHEME_INVERSE_VOL,
    CnAttackParameters,
)

# The 4-cell grid: 2 factor variants × 2 weighting schemes, exit fixed.
_FACTOR_VARIANTS = (FACTOR_VARIANT_QUALITY_MOMENTUM, FACTOR_VARIANT_PURE_MOMENTUM)
_WEIGHTING_SCHEMES = (WEIGHTING_SCHEME_EQUAL, WEIGHTING_SCHEME_INVERSE_VOL)
_FIXED_EXIT = EXIT_MOMENTUM_DECAY

_IN_SAMPLE_FRACTION = 0.7  # walk-forward split: first 70% design, last 30% validation
_IMPLAUSIBLE_SHARPE = 3.0  # a daily-rebalanced A-share Sharpe above this is suspect
_INDISTINGUISHABLE_CAGR_SPREAD = 0.01  # within 1% CAGR ⇒ the dimension is moot


@dataclass(frozen=True, slots=True)
class WideVariantMetrics:
    """Full-sample + walk-forward metrics for one (factor, weighting) config."""

    factor_variant: str
    weighting_scheme: str
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
    out_sample_max_drawdown: float


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    """CSI 300 benchmark metrics over the same window (or unavailable)."""

    available: bool
    cagr: float
    sharpe: float
    max_drawdown: float


@dataclass(frozen=True, slots=True)
class QuestionAnswers:
    """Data-driven verdicts for the three B066-open questions (Q1/Q2/Q3)."""

    q1_quality_verdict: str
    q1_evidence: str
    q2_inverse_vol_verdict: str
    q2_evidence: str
    q3_fragility_verdict: str
    q3_evidence: str


@dataclass(frozen=True, slots=True)
class CnAttackWideComparison:
    """All four configs + walk-forward + benchmark + flags + Q1/Q2/Q3 answers."""

    start: date
    end: date
    in_sample_end: date | None
    universe_breadth: int  # max members at any rebalance (wide vs seed evidence)
    variants: tuple[WideVariantMetrics, ...]
    benchmark: BenchmarkMetrics
    overfitting_flags: tuple[str, ...]
    answers: QuestionAnswers


# --------------------------------------------------------------------------- #
# Walk-forward + benchmark helpers (mirror B066's; kept local so B066 stays
# decoupled — the logic is generic, not exit/weighting specific)
# --------------------------------------------------------------------------- #


def _equity_segment(curve: pd.DataFrame, lo: pd.Timestamp, hi: pd.Timestamp) -> pd.DataFrame:
    seg = curve[(curve["date"] >= lo) & (curve["date"] <= hi)]
    return seg.reset_index(drop=True)


def _segment_metrics(segment: pd.DataFrame) -> tuple[float, float, float]:
    """(CAGR, Sharpe, MaxDD) for an equity-curve segment."""

    if len(segment) < 2:
        return 0.0, 0.0, 0.0
    returns = segment.set_index("date")["equity"].pct_change().dropna()
    return annualized_return(segment), sharpe_ratio(returns), max_drawdown(segment)


def _split_date(curve: pd.DataFrame) -> pd.Timestamp | None:
    if len(curve) < 4:
        return None
    dates = curve["date"].tolist()
    idx = max(1, min(len(dates) - 2, int(len(dates) * _IN_SAMPLE_FRACTION)))
    return pd.Timestamp(dates[idx])


def _variant_metrics(
    result: CnAttackBacktestResult, split: pd.Timestamp | None
) -> WideVariantMetrics:
    curve = result.equity_curve
    if split is None:
        in_cagr, in_sharpe = result.metrics.annualized_return, result.metrics.sharpe_ratio
        out_cagr, out_sharpe, out_dd = 0.0, 0.0, 0.0
    else:
        first = pd.Timestamp(curve["date"].iloc[0])
        last = pd.Timestamp(curve["date"].iloc[-1])
        in_cagr, in_sharpe, _ = _segment_metrics(_equity_segment(curve, first, split))
        out_cagr, out_sharpe, out_dd = _segment_metrics(_equity_segment(curve, split, last))
    return WideVariantMetrics(
        factor_variant=result.parameters.factor_variant,
        weighting_scheme=result.parameters.weighting_scheme,
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
        out_sample_max_drawdown=out_dd,
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


def _label(metrics: WideVariantMetrics) -> str:
    return f"{metrics.factor_variant}+{metrics.weighting_scheme}"


def _find(
    variants: tuple[WideVariantMetrics, ...], factor: str, weighting: str
) -> WideVariantMetrics | None:
    for variant in variants:
        if variant.factor_variant == factor and variant.weighting_scheme == weighting:
            return variant
    return None


# --------------------------------------------------------------------------- #
# Over-fitting red flags (§29) — weighting-aware
# --------------------------------------------------------------------------- #


def _overfitting_flags(
    variants: tuple[WideVariantMetrics, ...], has_out_sample: bool
) -> tuple[str, ...]:
    flags: list[str] = []
    if has_out_sample and len(variants) > 1:
        in_best = max(variants, key=lambda v: v.in_sample_sharpe)
        out_best = max(variants, key=lambda v: v.out_sample_sharpe)
        if _label(in_best) != _label(out_best):
            flags.append(
                "in_sample_winner_not_out_of_sample: in-sample best "
                f"({_label(in_best)}) ≠ out-of-sample best ({_label(out_best)}) "
                "— do NOT cherry-pick the in-sample winner"
            )
    implausible = [v for v in variants if v.sharpe > _IMPLAUSIBLE_SHARPE]
    if implausible:
        flags.append(
            "implausible_sharpe: "
            + ", ".join(f"{_label(v)} Sharpe={v.sharpe:.2f}" for v in implausible)
            + f" (> {_IMPLAUSIBLE_SHARPE}) — suspect / likely over-fit or too short a sample"
        )
    inert = [v for v in variants if v.rebalance_count == 0]
    if inert:
        flags.append(
            f"no_activity: {', '.join(_label(v) for v in inert)} never traded "
            "(empty cross-section / missing factor data) — its 0.00% is NOT a real result"
        )
    cagrs = [v.cagr for v in variants]
    if cagrs and (max(cagrs) - min(cagrs)) < _INDISTINGUISHABLE_CAGR_SPREAD:
        flags.append(
            f"indistinguishable_variants: all {len(variants)} configs within "
            f"{_INDISTINGUISHABLE_CAGR_SPREAD:.0%} CAGR — neither factor nor weighting "
            "meaningfully differentiates on this sample"
        )
    # Within a factor family, identical (CAGR, Sharpe) across the 2 weightings means
    # the weighting overlay provably never engaged (e.g. σ unavailable → inverse_vol
    # degraded to equal) — the weighting analogue of B066's exit_overlay_inert flag.
    for factor in sorted({v.factor_variant for v in variants}):
        family = [v for v in variants if v.factor_variant == factor]
        signatures = {(round(v.cagr, 6), round(v.sharpe, 6)) for v in family}
        if len(family) > 1 and len(signatures) == 1:
            flags.append(
                f"weighting_overlay_inert: the {len(family)} weightings for factor "
                f"'{factor}' are identical — inverse_vol never differed from equal "
                "(σ likely unavailable → degraded to equal weight)"
            )
    return tuple(flags)


# --------------------------------------------------------------------------- #
# Q1 / Q2 / Q3 — data-driven answers from the out-of-sample segment
# --------------------------------------------------------------------------- #


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%"


def _answer_q1(variants: tuple[WideVariantMetrics, ...]) -> tuple[str, str]:
    """Quality adds value if quality+momentum beats pure-momentum OOS Sharpe."""

    deltas: list[str] = []
    signs: list[int] = []
    for weighting in _WEIGHTING_SCHEMES:
        qm = _find(variants, FACTOR_VARIANT_QUALITY_MOMENTUM, weighting)
        pm = _find(variants, FACTOR_VARIANT_PURE_MOMENTUM, weighting)
        if qm is None or pm is None:
            continue
        d_sharpe = qm.out_sample_sharpe - pm.out_sample_sharpe
        d_cagr = qm.out_sample_cagr - pm.out_sample_cagr
        signs.append(1 if d_sharpe > 0 else (-1 if d_sharpe < 0 else 0))
        deltas.append(
            f"[{weighting}] OOS Sharpe Δ(quality−pure)={d_sharpe:+.2f} "
            f"(quality {qm.out_sample_sharpe:.2f} vs pure {pm.out_sample_sharpe:.2f}), "
            f"OOS CAGR Δ={_fmt_pct(d_cagr)}"
        )
    if not signs:
        return "inconclusive", "insufficient data to compare quality vs pure momentum"
    if all(s > 0 for s in signs):
        verdict = "yes — quality adds OOS value in both weightings"
    elif all(s < 0 for s in signs):
        verdict = "no — quality does NOT add OOS value (pure momentum ≥ quality)"
    else:
        verdict = "mixed — quality helps under one weighting only"
    return verdict, "; ".join(deltas)


def _answer_q2(variants: tuple[WideVariantMetrics, ...]) -> tuple[str, str]:
    """Inverse-vol tames the crash if it reduces |OOS MaxDD| / raises OOS Sharpe."""

    notes: list[str] = []
    dd_better: list[int] = []
    for factor in _FACTOR_VARIANTS:
        eq = _find(variants, factor, WEIGHTING_SCHEME_EQUAL)
        iv = _find(variants, factor, WEIGHTING_SCHEME_INVERSE_VOL)
        if eq is None or iv is None:
            continue
        # MaxDD is <= 0; "less deep" = closer to 0 = larger value.
        dd_delta = iv.out_sample_max_drawdown - eq.out_sample_max_drawdown
        sharpe_delta = iv.out_sample_sharpe - eq.out_sample_sharpe
        dd_better.append(1 if dd_delta > 0 else (-1 if dd_delta < 0 else 0))
        notes.append(
            f"[{factor}] OOS MaxDD equal {_fmt_pct(eq.out_sample_max_drawdown)} → "
            f"inverse_vol {_fmt_pct(iv.out_sample_max_drawdown)} (Δ={_fmt_pct(dd_delta)}), "
            f"OOS Sharpe Δ(iv−eq)={sharpe_delta:+.2f}"
        )
    if not dd_better:
        return "inconclusive", "insufficient data to compare equal vs inverse_vol"
    if all(s > 0 for s in dd_better):
        verdict = "yes — inverse_vol shrinks the OOS drawdown in both factors"
    elif all(s < 0 for s in dd_better):
        verdict = "no — inverse_vol does NOT reduce the OOS drawdown"
    else:
        verdict = "mixed — inverse_vol helps the drawdown in one factor only"
    return verdict, "; ".join(notes)


def _answer_q3(variants: tuple[WideVariantMetrics, ...]) -> tuple[str, str]:
    """Still fragile if the OOS segment is broadly negative / much worse than IS."""

    if not variants:
        return "inconclusive", "no variants"
    negative_oos = [v for v in variants if v.out_sample_cagr < 0]
    degraded = [v for v in variants if v.out_sample_sharpe < v.in_sample_sharpe]
    notes = "; ".join(
        f"{_label(v)} IS Sharpe {v.in_sample_sharpe:.2f}→OOS {v.out_sample_sharpe:.2f}, "
        f"OOS CAGR {_fmt_pct(v.out_sample_cagr)}"
        for v in variants
    )
    if len(negative_oos) >= max(1, len(variants) // 2):
        verdict = (
            f"yes — still fragile: {len(negative_oos)}/{len(variants)} configs have "
            "NEGATIVE OOS CAGR (the B066 momentum-reversal pattern persists on the wider OOS)"
        )
    elif len(degraded) == len(variants):
        verdict = "partly — all configs degrade IS→OOS, but OOS CAGR stays non-negative"
    else:
        verdict = "no — the wider OOS is not uniformly fragile (OOS broadly holds up)"
    return verdict, notes


def _build_answers(variants: tuple[WideVariantMetrics, ...]) -> QuestionAnswers:
    q1_verdict, q1_evidence = _answer_q1(variants)
    q2_verdict, q2_evidence = _answer_q2(variants)
    q3_verdict, q3_evidence = _answer_q3(variants)
    return QuestionAnswers(
        q1_quality_verdict=q1_verdict,
        q1_evidence=q1_evidence,
        q2_inverse_vol_verdict=q2_verdict,
        q2_evidence=q2_evidence,
        q3_fragility_verdict=q3_verdict,
        q3_evidence=q3_evidence,
    )


# --------------------------------------------------------------------------- #
# Orchestrator + renderers
# --------------------------------------------------------------------------- #


def build_cn_attack_wide_comparison(
    start: date,
    end: date,
    *,
    prices: pd.DataFrame,
    fundamentals: pd.DataFrame | None,
    universe_history: dict[date, tuple[str, ...]],
    benchmark: pd.Series | None = None,
    config: CnAttackBacktestConfig | None = None,
) -> CnAttackWideComparison:
    """Run the 4-config grid (factor × weighting, exit fixed), split walk-forward,
    compare vs CSI 300, flag over-fit, and answer Q1/Q2/Q3.

    ``config`` supplies the non-variant knobs (capital, band, cost model); the exit
    is pinned to ``momentum_decay`` regardless of ``config.exit_variant`` (the
    data-snooping discipline). ``benchmark`` defaults to the on-disk CSI 300.
    """

    base = config or CnAttackBacktestConfig()
    if benchmark is None:
        benchmark = load_cn_benchmark(start, end)

    results: list[CnAttackBacktestResult] = []
    for factor in _FACTOR_VARIANTS:
        for weighting in _WEIGHTING_SCHEMES:
            params = CnAttackParameters(factor_variant=factor, weighting_scheme=weighting)
            cfg = CnAttackBacktestConfig(
                starting_capital=base.starting_capital,
                cost_model=base.cost_model,
                no_trade_band=base.no_trade_band,
                exit_variant=_FIXED_EXIT,
                trailing_stop_pct=base.trailing_stop_pct,
                profit_target_pct=base.profit_target_pct,
            )
            results.append(
                run_cn_attack_backtest(
                    params,
                    cfg,
                    start,
                    end,
                    prices=prices,
                    fundamentals=fundamentals,
                    universe_history=universe_history,
                )
            )

    split = _split_date(results[0].equity_curve)
    variants = tuple(_variant_metrics(result, split) for result in results)
    lo = pd.Timestamp(results[0].equity_curve["date"].iloc[0])
    hi = pd.Timestamp(results[0].equity_curve["date"].iloc[-1])
    breadth = max((len(m) for m in universe_history.values()), default=0)

    return CnAttackWideComparison(
        start=start,
        end=end,
        in_sample_end=split.date() if split is not None else None,
        universe_breadth=breadth,
        variants=variants,
        benchmark=_benchmark_metrics(benchmark, lo, hi),
        overfitting_flags=_overfitting_flags(variants, has_out_sample=split is not None),
        answers=_build_answers(variants),
    )


def run_cn_attack_wide_comparison(
    start: date | None = None,
    end: date | None = None,
    *,
    config: CnAttackBacktestConfig | None = None,
) -> CnAttackWideComparison:
    """Load the unified CN data from the data root and run the 4-config comparison.

    Point ``WORKBENCH_DATA_ROOT`` at the B068 research root (wide prices /
    fundamentals / universe / benchmark) so the existing loaders read exactly the
    wide research data — the live B067 surface (seed-43, production data root) is
    untouched.
    """

    from trade.data.cn_attack_universe import load_cn_universe_history
    from trade.data.us_quality_universe import load_fundamentals, load_prices

    prices = load_prices()
    if prices.empty:
        raise ValueError("no price data available for the CN attack wide comparison")
    if start is None:
        start = (
            pd.Timestamp(prices["date"].min()) + pd.DateOffset(months=DEFAULT_WARMUP_MONTHS)
        ).date()
    if end is None:
        end = pd.Timestamp(prices["date"].max()).date()
    return build_cn_attack_wide_comparison(
        start,
        end,
        prices=prices,
        fundamentals=load_fundamentals(),
        universe_history=load_cn_universe_history(),
        benchmark=load_cn_benchmark(start, end),
        config=config,
    )


def build_cn_attack_wide_payload(
    comparison: CnAttackWideComparison, run_id: str
) -> dict[str, object]:
    """JSON payload: 4-config metrics + walk-forward + benchmark + flags + Q1/Q2/Q3."""

    return {
        "run": {"run_id": run_id, "strategy": "cn_attack_wide_revalidation", "research_only": True},
        "window": {
            "start": comparison.start.isoformat(),
            "end": comparison.end.isoformat(),
            "in_sample_end": (
                comparison.in_sample_end.isoformat() if comparison.in_sample_end else None
            ),
        },
        "universe_breadth": comparison.universe_breadth,
        "variants": [
            {
                "factor_variant": v.factor_variant,
                "weighting_scheme": v.weighting_scheme,
                "CAGR": v.cagr,
                "Sharpe": v.sharpe,
                "max_drawdown": v.max_drawdown,
                "turnover": v.turnover,
                "transaction_costs": v.total_cost,
                "rebalance_count": v.rebalance_count,
                "in_sample_CAGR": v.in_sample_cagr,
                "in_sample_Sharpe": v.in_sample_sharpe,
                "out_sample_CAGR": v.out_sample_cagr,
                "out_sample_Sharpe": v.out_sample_sharpe,
                "out_sample_max_drawdown": v.out_sample_max_drawdown,
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
        "answers": {
            "Q1_quality_adds_value": {
                "verdict": comparison.answers.q1_quality_verdict,
                "evidence": comparison.answers.q1_evidence,
            },
            "Q2_inverse_vol_tames_crash": {
                "verdict": comparison.answers.q2_inverse_vol_verdict,
                "evidence": comparison.answers.q2_evidence,
            },
            "Q3_oos_still_fragile": {
                "verdict": comparison.answers.q3_fragility_verdict,
                "evidence": comparison.answers.q3_evidence,
            },
        },
    }


def render_cn_attack_wide_markdown(comparison: CnAttackWideComparison) -> str:
    """Bilingual research report: 4-config table + walk-forward + 沪深300 + Q1/Q2/Q3 + 红旗."""

    a = comparison.answers
    lines: list[str] = [
        "# A股 进攻策略 宽宇宙重验 — 4 配置对比报告（研究态 research-only）",
        "",
        f"- 回测区间 / Window: {comparison.start.isoformat()} → {comparison.end.isoformat()}",
        "- 样本内/外切分 / In-sample split: "
        + (comparison.in_sample_end.isoformat() if comparison.in_sample_end else "n/a"),
        f"- 宇宙广度 / Universe breadth: 每期最多 {comparison.universe_breadth} 名 "
        "(B066 seed-43 → 本批宽宇宙)",
        "",
        "> 研究纪律：4 配置（2 因子 × 2 权重，退出固定 momentum_decay）**全部披露**，"
        "不 cherry-pick 样本内赢家；判定以**样本外**为准。research-only / 无实盘 / 无执行。",
        "",
        "## 全样本对比 / Full-sample comparison",
        "",
        "| 因子 Factor | 权重 Weighting | CAGR | Sharpe | MaxDD | 换手 | 成本 | 调仓 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for v in comparison.variants:
        lines.append(
            f"| {v.factor_variant} | {v.weighting_scheme} | {_fmt_pct(v.cagr)} | "
            f"{v.sharpe:.2f} | {_fmt_pct(v.max_drawdown)} | {v.turnover:.2f} | "
            f"{v.total_cost:.0f} | {v.rebalance_count} |"
        )
    lines += [
        "",
        "## Walk-forward 样本外验证 / Out-of-sample validation",
        "",
        "| Factor | Weighting | IS CAGR | IS Sharpe | OOS CAGR | OOS Sharpe | OOS MaxDD |",
        "|---|---|---|---|---|---|---|",
    ]
    for v in comparison.variants:
        lines.append(
            f"| {v.factor_variant} | {v.weighting_scheme} | {_fmt_pct(v.in_sample_cagr)} | "
            f"{v.in_sample_sharpe:.2f} | {_fmt_pct(v.out_sample_cagr)} | "
            f"{v.out_sample_sharpe:.2f} | {_fmt_pct(v.out_sample_max_drawdown)} |"
        )
    lines += ["", "## 基准 / Benchmark — 沪深300 (CSI 300)", ""]
    if comparison.benchmark.available:
        bench = comparison.benchmark
        lines.append(
            f"- CAGR {_fmt_pct(bench.cagr)} / Sharpe {bench.sharpe:.2f} / "
            f"MaxDD {_fmt_pct(bench.max_drawdown)}"
        )
    else:
        lines.append("- ⚠️ 基准数据不可用 / benchmark unavailable（沪深300 CSV 缺失）。")
    lines += [
        "",
        "## 三问 / The three questions（样本外为准）",
        "",
        f"**Q1 — 质量是否加值 / Does quality add value?** {a.q1_quality_verdict}",
        f"  - 证据 / Evidence: {a.q1_evidence}",
        "",
        f"**Q2 — 波动倒数能否驯服 OOS 崩盘 / Does inverse-vol tame the OOS crash?** "
        f"{a.q2_inverse_vol_verdict}",
        f"  - 证据 / Evidence: {a.q2_evidence}",
        "",
        f"**Q3 — 更宽/更长 OOS 是否仍脆弱 / Is the wider OOS still fragile?** "
        f"{a.q3_fragility_verdict}",
        f"  - 证据 / Evidence: {a.q3_evidence}",
        "",
        "## 过拟合红旗 / Over-fitting red flags",
        "",
    ]
    if comparison.overfitting_flags:
        lines += [f"- 🚩 {flag}" for flag in comparison.overfitting_flags]
    else:
        lines.append("- 无显著红旗（仍以样本外为准，区间短则谨慎）/ none flagged.")
    lines += [
        "",
        "## 研究判定指引 / Research verdict (F004 Codex 终判)",
        "",
        "- 据**样本外**：(a) 质量是否加值 (b) 波动倒数是否值得换 "
        "(c) 是否建议调 B067 实盘默认配置。",
        "- research-only：无实盘 / 无执行 / 无收益预测 / 不碰 live；本批不改 B067 surface。",
    ]
    return "\n".join(lines)


__all__ = [
    "BenchmarkMetrics",
    "CnAttackWideComparison",
    "QuestionAnswers",
    "WideVariantMetrics",
    "build_cn_attack_wide_comparison",
    "build_cn_attack_wide_payload",
    "render_cn_attack_wide_markdown",
    "run_cn_attack_wide_comparison",
]
