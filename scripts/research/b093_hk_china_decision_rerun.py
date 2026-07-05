#!/usr/bin/env python
"""B093 F001 — decision-grade real-vs-proxy HK/China rerun (matched top_n).

Research-only (touches NO strategy/production code; hk_china stays ETF-proxy for
LIVE). Extends the B090 retest (:mod:`scripts.research.b090_hk_china_retest`)
with the two things a decision needs:

1. **The B091-O1 close-NaN residual fix, quantified.** B091 fixed the 200D-MA to
   each ticker's own calendar, but the compared close was still the union
   frame's raw last row (``wide.iloc[-1]``) — NaN whenever the union's last date
   is a holiday for a ticker → a spurious "below MA" / false-defensive. B093
   fixes it to each ticker's own last valid close (``wide.ffill().iloc[-1]``).
   This script re-runs the real sleeve's per-quarter defensive decision with the
   FIXED factor and with the pre-fix BUGGY close and reports how many
   false-defensive quarters the fix removed.

2. **A matched-top_n comparison.** B090 compared proxy top_n=2 against real
   top_n=6 — different breadth, so any edge conflated concentration with
   data-source. The proxy engine hard-caps ``top_n`` to 1 or 2 (design §8.2 "Top
   1-2"), so the LARGEST N both engines can hold is **2**. We therefore report
   the fair matched run at top_n=2 on BOTH sides (proxy default already 2; real
   forced to 2), alongside the default top_n=6 real for reference.

Reuses the cached B090 data in ``data/research/b090_hk`` (no re-fetch).

Run:  workbench/backend/.venv/bin/python -m scripts.research.b093_hk_china_decision_rerun
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd

import trade.strategies.hk_china_momentum.factors as factors
from scripts.research.b090_hk_china_retest import (
    _DEFENSIVE_ASSET,
    _FX_CSV,
    _UNIFIED_CSV,
    _defensive_asset_floor,
    defensive_reason_breakdown,
)
from trade.backtest.hk_china_comparison import ComparisonResult
from trade.backtest.hk_china_comparison_runner import (
    build_usd_frames,
    run_proxy_vs_real_comparison,
    shared_quarterly_signal_dates,
)
from trade.backtest.monthly import BacktestParameters
from trade.data.fx import FxConverter
from trade.strategies.hk_china_momentum.factors import (
    _latest_ma_own_calendar,
    _wide_close,
)
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters

# The proxy momentum engine hard-caps top_n to {1, 2} (design §8.2 Top 1-2), so
# the largest number of names BOTH engines can hold is 2. That is the matched N.
_MATCHED_TOP_N = 2
_REFERENCE_REAL_TOP_N = 6  # the B090 default, kept for context


def _buggy_close_above_200d_ma(
    prices: pd.DataFrame, as_of: date, ma_long: int = factors.DEFAULT_MA_LONG
) -> pd.Series:
    """The PRE-B093 implementation: own-calendar MA (B091) but the residual
    close bug ``close = wide.iloc[-1]`` (raw union last row, may be NaN)."""

    wide = _wide_close(prices, as_of)
    if wide.empty:
        return pd.Series(dtype=bool)
    close = wide.iloc[-1]
    ma = wide.apply(lambda col: _latest_ma_own_calendar(col, ma_long))
    return (close > ma).fillna(False)


@contextmanager
def _buggy_close_patch() -> Iterator[None]:
    """Temporarily swap in the pre-B093 raw-last-row close. ``trend_pass`` and
    ``regional_risk_off`` resolve ``above_200d_ma`` from the module globals at
    call time, so patching the module attribute reproduces the buggy decision."""

    original = factors.above_200d_ma
    factors.above_200d_ma = _buggy_close_above_200d_ma  # type: ignore[assignment]
    try:
        yield
    finally:
        factors.above_200d_ma = original  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class DecisionRerun:
    scored_window_start: date
    signal_dates: tuple[date, ...]
    matched: ComparisonResult  # both sides top_n=2
    reference_real_top6: ComparisonResult  # proxy top2 vs real top6 (B090 caliber)
    reasons_fixed: Counter[str]
    reasons_buggy: Counter[str]


def _run_comparison(
    unified: pd.DataFrame,
    converter: FxConverter,
    signal_dates: tuple[date, ...],
    *,
    real_top_n: int,
) -> ComparisonResult:
    proxy_usd, real_usd = build_usd_frames(
        unified,
        converter,
        proxy_defensive_asset=_DEFENSIVE_ASSET,
        real_defensive_asset=_DEFENSIVE_ASSET,
    )
    return run_proxy_vs_real_comparison(
        proxy_usd_prices=proxy_usd,
        real_usd_prices=real_usd,
        signal_dates=signal_dates,
        proxy_parameters=HkChinaMomentumParameters(top_n=_MATCHED_TOP_N),
        real_parameters=HkChinaRealParameters(top_n=real_top_n),
        backtest_parameters=BacktestParameters(),
    )


def run_decision_rerun(
    unified: pd.DataFrame, converter: FxConverter
) -> DecisionRerun:
    proxy_usd, real_usd = build_usd_frames(
        unified,
        converter,
        proxy_defensive_asset=_DEFENSIVE_ASSET,
        real_defensive_asset=_DEFENSIVE_ASSET,
    )
    all_signals = shared_quarterly_signal_dates(proxy_usd, real_usd)
    floor = _defensive_asset_floor(unified)
    scored = tuple(d for d in all_signals if d >= floor)
    if not scored:
        raise SystemExit("no signal dates on/after the SGOV pricing floor")

    matched = _run_comparison(unified, converter, scored, real_top_n=_MATCHED_TOP_N)
    reference = _run_comparison(
        unified, converter, scored, real_top_n=_REFERENCE_REAL_TOP_N
    )

    # Close-NaN residual: real defensive-reason breakdown, fixed vs buggy close.
    # top_n does not change the defensive/participate decision (that is upstream
    # of ranking), so we probe once at the matched N.
    real_params = HkChinaRealParameters(top_n=_MATCHED_TOP_N)
    reasons_fixed = defensive_reason_breakdown(real_usd, scored, real_params)
    with _buggy_close_patch():
        reasons_buggy = defensive_reason_breakdown(real_usd, scored, real_params)

    return DecisionRerun(
        scored_window_start=floor,
        signal_dates=scored,
        matched=matched,
        reference_real_top6=reference,
        reasons_fixed=reasons_fixed,
        reasons_buggy=reasons_buggy,
    )


def _fmt(value: float) -> str:
    return f"{value:+.4f}"


def _defensive_count(reasons: Counter[str]) -> int:
    return sum(c for r, c in reasons.items() if r != "selected_top_n")


def _print_report(rerun: DecisionRerun) -> None:
    n = len(rerun.signal_dates)
    print(
        f"\nSGOV pricing floor: {rerun.scored_window_start} -> {n} runnable scored "
        f"quarters ({rerun.signal_dates[0]}..{rerun.signal_dates[-1]})"
    )

    print("\n=== CLOSE-NaN RESIDUAL FIX (B091-O1), real sleeve, matched top_n=2 ===")
    print(f"  {'reason':<24}{'FIXED (ffill)':>16}{'BUGGY (iloc[-1])':>18}")
    all_reasons = sorted(set(rerun.reasons_fixed) | set(rerun.reasons_buggy))
    for reason in all_reasons:
        f = rerun.reasons_fixed.get(reason, 0)
        b = rerun.reasons_buggy.get(reason, 0)
        print(f"  {reason:<24}{f:>16}/{n}{b:>15}/{n}")
    def_fixed = _defensive_count(rerun.reasons_fixed)
    def_buggy = _defensive_count(rerun.reasons_buggy)
    print(
        f"  -> defensive quarters: FIXED {def_fixed}/{n}  vs  BUGGY {def_buggy}/{n} "
        f"=> close-NaN fix removed {def_buggy - def_fixed} false-defensive quarter(s)"
    )
    participation = (n - def_fixed) / n
    print(
        f"  -> real participation (holds stocks): {n - def_fixed}/{n} = "
        f"{participation:.1%}"
    )

    def _table(label: str, result: ComparisonResult) -> None:
        p, r = result.proxy, result.real
        print(f"\n=== {label} ===")
        print(f"{'metric':<26}{'proxy':>14}{'real':>14}")
        rows = (
            ("CAGR", p.metrics.cagr, r.metrics.cagr),
            ("Sharpe", p.metrics.sharpe, r.metrics.sharpe),
            ("annualized_vol", p.metrics.annualized_volatility,
             r.metrics.annualized_volatility),
            ("max_drawdown", p.metrics.max_drawdown, r.metrics.max_drawdown),
        )
        for name, pv, rv in rows:
            print(f"{name:<26}{_fmt(pv):>14}{_fmt(rv):>14}")
        print(f"{'defensive_periods':<26}{p.defensive_periods:>14}"
              f"{r.defensive_periods:>14}")
        print(f"{'forced_defensive_periods':<26}{p.forced_defensive_periods:>14}"
              f"{r.forced_defensive_periods:>14}")
        print(f"{'selection_top_n':<26}{p.selection_top_n:>14}{r.selection_top_n:>14}")
        print(f"{'avg_holdings':<26}{p.avg_holdings:>14.2f}{r.avg_holdings:>14.2f}")

    _table("MATCHED top_n=2 (proxy 2 vs real 2 — fair, isolates data-source)",
           rerun.matched)
    _table("REFERENCE (proxy top_n=2 vs real top_n=6 — B090 caliber, breadth gap)",
           rerun.reference_real_top6)


def _load_unified() -> pd.DataFrame:
    if not _UNIFIED_CSV.is_file():
        raise SystemExit(f"missing {_UNIFIED_CSV} — run b090_hk_china_fetch first")
    return pd.read_csv(_UNIFIED_CSV, dtype={"ticker": str})


def main() -> int:
    unified = _load_unified()
    converter = FxConverter.load(path=_FX_CSV)
    print(
        f"loaded {Path(_UNIFIED_CSV).name}: {len(unified)} rows, "
        f"{unified['ticker'].nunique()} tickers"
    )
    rerun = run_decision_rerun(unified, converter)
    _print_report(rerun)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
