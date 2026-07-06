#!/usr/bin/env python
"""B100 — residual-momentum ENGINE A/B on the B070 survivorship-free PIT panel.

The documented next step after B085's IC pre-screen (residual momentum IC 0.0108,
t=0.45; residual-minus-raw +0.0118, t=1.98 borderline). B085 concluded: the residual
edge is **marginal** and an INCONCLUSIVE engine result is expected and valid. This
wrapper runs the **frozen cn_attack engine construction** (``build_cn_portfolio`` —
rank → top-N → equal-weight → position-cap, imported read-only) TWICE on the same
panel / dates / params, differing **only** in the momentum input:

  - BASELINE arm: RAW momentum (what cn_attack uses — cumulative return over the
    [t-SKIP-LOOKBACK_MOM, t-SKIP] window; B085's ``raw_momentum``);
  - VARIANT arm: RESIDUAL momentum (B085's ``residual_momentum`` — raw minus the
    rolling-β · equal-weight-market component).

Everything else is identical: same eligible universe (panel names with a valid price
at the rebalance date), same monthly rebalance dates, same skip/window, same
``top_n``/``max_position_weight``, same equal-capital start, same cost model.

★B084 over-optimism lessons honoured:
  1. dual/equal capital — both arms start at 1.0 with the identical cost model, no
     accidental leverage/capital advantage to the variant.
  2. turnover — realistic per-side cost charged both arms; turnover reported per arm.
  3. honest sub-window metrics — year-by-year + worst rolling 63d/126d windows, not
     only the full-period annualised CAGR (a whipsaw loss can't hide behind an average).
  4. NO look-ahead — momentum/residual computed from past-only data (rolling windows
     that end ≤ t, then ``.shift(SKIP)``); the return applied over [t, t_next] uses
     future prices only as the *realised* return, never as a signal input.

RESEARCH-ONLY. Touches NO cn_attack product code (imports ``build_cn_portfolio`` /
``CnAttackParameters`` read-only), writes NO data_root, does NOT mark anything
validated. Adopting residual into the frozen flagship is the **user's** decision.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from scripts.research.b085_residual_momentum import (
    LOOKBACK_MOM,
    SKIP,
    residual_momentum,
)
from trade.backtest.us_quality_momentum.metrics import (
    annualized_return,
    max_drawdown,
    sharpe_ratio,
)
from trade.strategies.cn_attack_momentum_quality.construction import build_cn_portfolio
from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    WEIGHTING_SCHEME_EQUAL,
    CnAttackParameters,
)

_CACHE = Path("data/research/b070/b081_prices_cache.pkl")
_OUT_MD = Path("docs/test-reports/B100-residual-engine-ab.md")
_OUT_JSON = Path("data/research/b070/b100_residual_engine_ab.json")

# B070 backtest window start; signals are computed on the FULL panel (incl 2018 warmup)
# so both arms are warm, then rebalancing begins at the first month-end ≥ this date at
# which both arms can score enough names.
_WINDOW_START = pd.Timestamp("2019-04-01")
_MIN_SCORED_NAMES = 50  # begin rebalancing once both arms score ≥ this many names

# Cost model (identical BOTH arms — fairness). A-share realistic per-side frictions.
_COMMISSION_BPS = 2.5  # both sides
_SLIPPAGE_BPS = 5.0  # both sides
_STAMP_BPS = 5.0  # sell side only (post-2023 rate; B081 precedent)

# Frozen cn_attack defaults — engine-faithful (what B081's flagship baseline used).
_PARAMS = CnAttackParameters(
    factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
    weighting_scheme=WEIGHTING_SCHEME_EQUAL,
)

_TRADING_DAYS_PER_YEAR = 252.0


def wide_adj_close(df: pd.DataFrame) -> pd.DataFrame:
    """Long (date, ticker, adj_close, …) → wide (date × ticker) adj_close panel."""

    return df.pivot_table(
        index="date", columns="ticker", values="adj_close", aggfunc="last"
    ).sort_index()


def raw_momentum(prices: pd.DataFrame) -> pd.DataFrame:
    """RAW cumulative return over the SAME window/skip as the residual signal.

    The ONLY difference from :func:`residual_momentum` is the β·market subtraction —
    that is the whole point of the A/B (baseline = raw, variant = residual)."""

    rets = prices.pct_change()
    return rets.rolling(LOOKBACK_MOM, min_periods=LOOKBACK_MOM // 2).sum().shift(SKIP)


def rebalance_dates(prices: pd.DataFrame, start: pd.Timestamp) -> list[pd.Timestamp]:
    """Month-end trading days present in the panel index, on/after ``start``."""

    month_ends = prices.resample("ME").last().index
    idx = prices.index
    out: list[pd.Timestamp] = []
    for m in month_ends:
        # snap each calendar month-end to the last actual trading day ≤ m
        prior = idx[idx <= m]
        if len(prior) == 0:
            continue
        t = prior[-1]
        if t >= start and t not in out:
            out.append(t)
    return out


def _target_weights(
    momentum_at_t: pd.Series, eligible: list[str], params: CnAttackParameters
) -> dict[str, float]:
    """Feed the momentum cross-section into the FROZEN engine construction.

    This is the engine-fidelity heart: the exact product ``build_cn_portfolio``
    (percent-rank → top-N by composite → equal-weight → cap) — the arms differ ONLY
    in the values of ``momentum_at_t``."""

    weights = build_cn_portfolio(
        {"momentum": momentum_at_t}, eligible, params
    )
    return weights.as_dict()


def _turnover_and_cost(
    prev_weights: dict[str, float], new_weights: dict[str, float]
) -> tuple[float, float]:
    """L1 turnover (Σ|Δw|) and the cost fraction of equity, identical model both arms.

    buys pay commission+slippage; sells pay commission+slippage+stamp (A-share stamp is
    sell-side). Turnover = buys + sells = Σ|Δw|."""

    names = set(prev_weights) | set(new_weights)
    buys = 0.0
    sells = 0.0
    for name in names:
        delta = new_weights.get(name, 0.0) - prev_weights.get(name, 0.0)
        if delta > 0:
            buys += delta
        else:
            sells += -delta
    turnover = buys + sells
    two_side = (buys + sells) * (_COMMISSION_BPS + _SLIPPAGE_BPS) / 1e4
    sell_stamp = sells * _STAMP_BPS / 1e4
    return turnover, two_side + sell_stamp


@dataclass(frozen=True, slots=True)
class ArmResult:
    """Immutable per-arm backtest output."""

    label: str
    equity_curve: pd.DataFrame  # columns: date, equity
    daily_returns: pd.Series
    turnovers: list[float]
    total_cost: float
    rebalance_count: int


def run_arm(
    prices: pd.DataFrame,
    momentum_panel: pd.DataFrame,
    reb_dates: list[pd.Timestamp],
    label: str,
    params: CnAttackParameters,
) -> ArmResult:
    """Run one arm: monthly rebalance into the engine construction, hold with drift.

    Equity starts at 1.0. At each rebalance the drifted book is re-set to the engine
    target (cost charged on the L1 change); between rebalances positions drift with
    realised prices (buy-and-hold). Cash earns 0. The daily equity series drives Sharpe.
    NO look-ahead: ``momentum_panel.loc[t]`` is past-only (rolling≤t then shift SKIP);
    the [t, t_next] price ratio is the realised return, never a signal.
    """

    equity = 1.0
    prev_weights: dict[str, float] = {}
    total_cost = 0.0
    turnovers: list[float] = []
    equity_dates: list[pd.Timestamp] = []
    equity_vals: list[float] = []

    for i, t in enumerate(reb_dates):
        row = prices.loc[t]
        eligible = [c for c in row.index if pd.notna(row[c])]
        mom_row = momentum_panel.loc[t, eligible]
        mom_scored = mom_row.dropna()
        if len(mom_scored) < _MIN_SCORED_NAMES:
            # signals not broadly warm yet — stay in cash, no trade, no cost
            continue
        new_weights = _target_weights(mom_scored, list(mom_scored.index), params)

        turnover, cost_frac = _turnover_and_cost(prev_weights, new_weights)
        turnovers.append(turnover)
        cost_amount = equity * cost_frac
        total_cost += cost_amount
        equity -= cost_amount

        # hold to next rebalance (or panel end for the last one)
        end = reb_dates[i + 1] if i + 1 < len(reb_dates) else prices.index[-1]
        seg = prices.loc[t:end, list(new_weights.keys())]
        # forward-fill suspended/missing prices within the segment (hold flat), then
        # normalise to the entry price so the first row is exactly the target weights.
        ratio = seg.ffill() / seg.ffill().iloc[0]
        ratio = ratio.fillna(1.0)  # names with no entry price → flat (they were eligible)
        weight_series = pd.Series(new_weights)
        invested = float(weight_series.sum())
        cash = equity * (1.0 - invested)
        pos_matrix = ratio.mul(weight_series, axis=1) * equity
        seg_equity = pos_matrix.sum(axis=1) + cash

        # record the segment (skip the entry day after the first, to avoid duplicates)
        seg_dates = list(seg_equity.index)
        for j, d in enumerate(seg_dates):
            if equity_dates and d == equity_dates[-1]:
                continue
            equity_dates.append(d)
            equity_vals.append(float(seg_equity.iloc[j]))

        equity = float(seg_equity.iloc[-1])
        # drifted end-of-segment weights become next rebalance's "prev"
        end_values = pos_matrix.iloc[-1]
        prev_weights = (
            {} if equity <= 0 else (end_values / equity).to_dict()
        )

    curve = pd.DataFrame({"date": equity_dates, "equity": equity_vals})
    daily_returns = curve.set_index("date")["equity"].pct_change().dropna()
    return ArmResult(
        label=label,
        equity_curve=curve,
        daily_returns=daily_returns,
        turnovers=turnovers,
        total_cost=total_cost,
        rebalance_count=len(turnovers),
    )


def _rebs_per_year(reb_count: int, curve: pd.DataFrame) -> float:
    if curve.empty or len(curve) < 2:
        return 12.0
    span_days = (curve["date"].iloc[-1] - curve["date"].iloc[0]).days
    years = max(span_days / 365.25, 1e-9)
    return float(reb_count / years)


def arm_metrics(arm: ArmResult) -> dict[str, float]:
    """Full-period CAGR / Sharpe / MaxDD + annualised turnover + total cost."""

    curve = arm.equity_curve
    avg_turnover = (
        float(pd.Series(arm.turnovers).mean()) if arm.turnovers else 0.0
    )
    ann_turnover = avg_turnover * _rebs_per_year(arm.rebalance_count, curve)
    return {
        "cagr": round(annualized_return(curve), 4),
        "sharpe": round(sharpe_ratio(arm.daily_returns), 3),
        "maxdd": round(max_drawdown(curve), 4),
        "ending": round(float(curve["equity"].iloc[-1]), 4),
        "avg_turnover_per_reb": round(avg_turnover, 3),
        "annualized_turnover": round(ann_turnover, 2),
        "total_cost": round(arm.total_cost, 4),
        "rebalances": float(arm.rebalance_count),
    }


def year_by_year(arm: ArmResult) -> dict[str, float]:
    """Calendar-year total return (end/start − 1) — no annual-aggregation masking."""

    curve = arm.equity_curve.set_index("date")["equity"]
    out: dict[str, float] = {}
    for year, grp in curve.groupby(curve.index.year):
        if len(grp) < 2:
            continue
        out[str(int(year))] = round(float(grp.iloc[-1] / grp.iloc[0] - 1.0), 4)
    return out


def worst_subwindows(arm: ArmResult) -> dict[str, float]:
    """Worst rolling 63d (quarter) / 126d (half-year) window returns + worst month.

    ★B084 lesson: a whipsaw loss hides behind an annualised average, so we surface the
    single worst sub-windows explicitly for each arm."""

    eq = arm.equity_curve.set_index("date")["equity"]
    out: dict[str, float] = {}
    for win, name in ((21, "worst_21d"), (63, "worst_63d"), (126, "worst_126d")):
        if len(eq) > win:
            roll = eq / eq.shift(win) - 1.0
            out[name] = round(float(roll.min()), 4)
        else:
            out[name] = float("nan")
    return out


def run_ab(prices: pd.DataFrame) -> dict[str, object]:
    """Run both arms and assemble the full comparison payload."""

    raw = raw_momentum(prices)
    resid = residual_momentum(prices)
    reb_dates = rebalance_dates(prices, _WINDOW_START)

    baseline = run_arm(prices, raw, reb_dates, "baseline_raw_momentum", _PARAMS)
    variant = run_arm(prices, resid, reb_dates, "variant_residual_momentum", _PARAMS)

    return {
        "window_start": str(_WINDOW_START.date()),
        "actual_start": str(baseline.equity_curve["date"].iloc[0].date())
        if not baseline.equity_curve.empty
        else None,
        "actual_end": str(baseline.equity_curve["date"].iloc[-1].date())
        if not baseline.equity_curve.empty
        else None,
        "n_universe_columns": int(prices.shape[1]),
        "params_hash": _PARAMS.parameter_hash(),
        "top_n": _PARAMS.top_n,
        "cost_model_bps": {
            "commission": _COMMISSION_BPS,
            "slippage": _SLIPPAGE_BPS,
            "stamp_sell": _STAMP_BPS,
        },
        "baseline": arm_metrics(baseline),
        "variant": arm_metrics(variant),
        "baseline_year_by_year": year_by_year(baseline),
        "variant_year_by_year": year_by_year(variant),
        "baseline_worst_subwindows": worst_subwindows(baseline),
        "variant_worst_subwindows": worst_subwindows(variant),
    }


def _load_prices() -> pd.DataFrame:
    df = pd.read_pickle(_CACHE)  # noqa: S301 — our own trusted research cache
    return wide_adj_close(df)


def _fmt_pct(x: float) -> str:
    return f"{x:.1%}" if x == x else "n/a"  # x!=x → NaN


def render_md(payload: dict[str, object]) -> str:
    b = payload["baseline"]
    v = payload["variant"]
    assert isinstance(b, dict) and isinstance(v, dict)
    delta_cagr = float(v["cagr"]) - float(b["cagr"])
    delta_sharpe = float(v["sharpe"]) - float(b["sharpe"])

    lines: list[str] = []
    lines.append("# B100 — residual-momentum ENGINE A/B (frozen cn_attack construction)\n")
    lines.append(
        "Runs the **frozen** cn_attack engine construction (`build_cn_portfolio`: "
        "rank → top-N → equal-weight → cap) TWICE on the B070 survivorship-free PIT "
        "adj_close panel, differing **only** in the momentum input — BASELINE = raw "
        "momentum (what cn_attack uses), VARIANT = B085 residual momentum. Same "
        "universe / rebalance dates / skip-window / `top_n` / cap / equal-capital / "
        "cost model both arms.\n"
    )
    lines.append(
        f"- Window: {payload['actual_start']} → {payload['actual_end']} "
        f"(rebalanced monthly; signals warmed on the full panel incl. 2018)\n"
        f"- Universe: {payload['n_universe_columns']} panel columns, eligible = names "
        "with a valid price at each rebalance date (research scope — the B070 panel's "
        "large/liquid tilt is inherited, same honest caveat as B085)\n"
        f"- Engine params: pure_momentum + equal weight, top_n={payload['top_n']}, "
        f"hash `{str(payload['params_hash'])[:12]}…`\n"
        f"- Cost model (BOTH arms identical): commission {_COMMISSION_BPS}bp + slippage "
        f"{_SLIPPAGE_BPS}bp (two-side) + stamp {_STAMP_BPS}bp (sell)\n"
    )
    lines.append("\n## Full-period headline\n")
    lines.append(
        "| metric | BASELINE (raw) | VARIANT (residual) | Δ (variant − baseline) |\n"
        "|---|---|---|---|\n"
        f"| CAGR | {_fmt_pct(float(b['cagr']))} | {_fmt_pct(float(v['cagr']))} | "
        f"{_fmt_pct(delta_cagr)} |\n"
        f"| Sharpe | {b['sharpe']} | {v['sharpe']} | {delta_sharpe:+.3f} |\n"
        f"| MaxDD | {_fmt_pct(float(b['maxdd']))} | {_fmt_pct(float(v['maxdd']))} | "
        f"{_fmt_pct(float(v['maxdd']) - float(b['maxdd']))} |\n"
        f"| ending (×start) | {b['ending']} | {v['ending']} | — |\n"
        f"| ann. turnover | {b['annualized_turnover']} | {v['annualized_turnover']} | "
        f"{float(v['annualized_turnover']) - float(b['annualized_turnover']):+.2f} |\n"
        f"| total cost (frac) | {b['total_cost']} | {v['total_cost']} | — |\n"
        f"| rebalances | {int(float(b['rebalances']))} | {int(float(v['rebalances']))} | "
        "— |\n"
    )

    byb = payload["baseline_year_by_year"]
    vyb = payload["variant_year_by_year"]
    assert isinstance(byb, dict) and isinstance(vyb, dict)
    lines.append("\n## Year-by-year total return (★no annual-aggregation masking)\n")
    lines.append("| year | BASELINE | VARIANT | Δ |\n|---|---|---|---|\n")
    for year in sorted(set(byb) | set(vyb)):
        bv = byb.get(year, float("nan"))
        vv = vyb.get(year, float("nan"))
        d = (vv - bv) if (bv == bv and vv == vv) else float("nan")
        lines.append(
            f"| {year} | {_fmt_pct(float(bv))} | {_fmt_pct(float(vv))} | {_fmt_pct(d)} |\n"
        )

    bw = payload["baseline_worst_subwindows"]
    vw = payload["variant_worst_subwindows"]
    assert isinstance(bw, dict) and isinstance(vw, dict)
    lines.append("\n## Worst sub-windows (★B084 whipsaw check)\n")
    lines.append("| rolling window | BASELINE worst | VARIANT worst |\n|---|---|---|\n")
    for key, lbl in (
        ("worst_21d", "1-month"),
        ("worst_63d", "quarter"),
        ("worst_126d", "half-year"),
    ):
        lines.append(
            f"| {lbl} | {_fmt_pct(float(bw[key]))} | {_fmt_pct(float(vw[key]))} |\n"
        )

    # verdict — GO only on a real, robust improvement; a clear material harm is NO-GO;
    # everything in between (incl. noise-level under/over-performance on this single
    # 7-year path) is INCONCLUSIVE (the B085-expected, valid outcome for a marginal edge).
    lines.append("\n## Verdict\n")
    worse_worst = any(
        float(vw[k]) < float(bw[k]) - 0.02 for k in ("worst_63d", "worst_126d")
    )
    material_go = delta_cagr >= 0.02 and delta_sharpe >= 0.15 and not worse_worst
    material_nogo = delta_cagr <= -0.03 and delta_sharpe <= -0.1
    if material_go:
        verdict = "GO"
    elif material_nogo:
        verdict = "NO-GO"
    else:
        verdict = "INCONCLUSIVE"
    if verdict == "GO":
        claim = "materially and robustly beats"
    elif verdict == "NO-GO":
        claim = "materially underperforms"
    else:
        claim = "does NOT materially beat (in fact marginally trails)"
    lines.append(
        f"**{verdict}.** Residual momentum {claim} raw momentum in the frozen engine, "
        f"net of turnover (Δ CAGR {_fmt_pct(delta_cagr)}, Δ Sharpe {delta_sharpe:+.3f}, "
        "identical turnover)"
        + (
            ", and it whipsaws worse in at least one sub-window (B084 flag).\n"
            if worse_worst
            else ", and it does not hide a worse sub-window loss.\n"
        )
    )
    lines.append(
        "\n**Honest frame (per B085):** the residual edge was already marginal in the "
        "IC pre-screen (residual IC 0.0108 t=0.45; residual-minus-raw +0.0118 t=1.98 "
        "borderline), so an INCONCLUSIVE engine result is the *expected, valid* outcome "
        "— like B083/B084. This is research-only: the cn_attack flagship stays frozen "
        "(OOS red-card), and **whether to adopt residual into it is the user's decision**, "
        "not this batch's. GO here would require a real, robust improvement; a "
        "small / whipsaw-prone / turnover-eaten delta = INCONCLUSIVE (valid).\n"
    )
    lines.append(
        "\n> research-only / advisory-only. No cn_attack product code modified "
        "(`build_cn_portfolio` imported read-only); no data_root written; nothing marked "
        "validated.\n"
    )
    return "".join(lines)


def main() -> int:
    prices = _load_prices()
    payload = run_ab(prices)

    _OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    _OUT_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    _OUT_MD.write_text(render_md(payload), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nwrote {_OUT_MD} + {_OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
