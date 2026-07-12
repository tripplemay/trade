#!/usr/bin/env python
"""Independent A-share monthly short-term reversal first-look.

This evaluator-only runner tests one frozen signal on the B070 point-in-time
universe: the negative of the trailing 20-session adjusted-price return at each
complete month-end.  It reuses the previously audited event-label and inference
helpers, but it does not call or modify the CN attack portfolio engine.

The primary question is deliberately stricter than a long-short anomaly test:
does the past-loser long leg earn a positive, statistically reliable excess over
the investable equal-weight universe?  The winner short leg is not implementable
in the user's cash A-share account and cannot make the candidate pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from scripts.test import ashare_multiscale_pv_trend_first_look as common

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = (
    REPO_ROOT
    / "docs"
    / "test-reports"
    / "ashare-short-term-reversal-first-look-2026-07-12.json"
)
TEST_PATH = REPO_ROOT / "tests" / "unit" / "test_ashare_short_term_reversal_first_look.py"
PAPER_DOI = "https://doi.org/10.1016/j.iref.2024.103653"
FORMATION_SESSIONS = 20
PRIMARY_HORIZON = "N20"
MIN_SIGNAL_MONTHS = 60
MIN_CROSS_SECTION = 100
MIN_COVERAGE = 0.95
MIN_MEAN_IC = 0.03
MIN_HAC_T = 2.0
MIN_LONG_EXCESS = 0.002
MIN_MONOTONICITY = 0.70


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _distribution(values: pd.Series | np.ndarray) -> dict[str, float | int | None]:
    sample = pd.Series(values, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if sample.empty:
        return {"n": 0, "min": None, "p10": None, "median": None, "max": None}
    return {
        "n": int(len(sample)),
        "min": float(sample.min()),
        "p10": float(sample.quantile(0.10)),
        "median": float(sample.median()),
        "max": float(sample.max()),
    }


def build_reversal_signals(
    close: pd.DataFrame,
    schedule: common.UniverseSchedule,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build strict month-end REV20 scores from information visible at formation."""

    ordered = close.sort_index()
    month_ends = common._complete_month_end_dates(ordered.index)
    rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    for signal_date in month_ends:
        position = int(ordered.index.get_indexer([signal_date])[0])
        if position < FORMATION_SESSIONS:
            continue
        members = sorted(schedule.members_on(signal_date))
        if len(members) < MIN_CROSS_SECTION:
            continue
        available = [ticker for ticker in members if ticker in ordered.columns]
        current = ordered.loc[signal_date, available].astype(float)
        anchor_date = ordered.index[position - FORMATION_SESSIONS]
        anchor = ordered.loc[anchor_date, available].astype(float)
        valid = current.notna() & anchor.notna() & current.gt(0) & anchor.gt(0)
        trailing_return = current[valid] / anchor[valid] - 1.0
        for ticker, value in trailing_return.items():
            rows.append(
                {
                    "signal_date": pd.Timestamp(signal_date),
                    "ticker": str(ticker),
                    "past_return_20": float(value),
                    "reversal_20": float(-value),
                }
            )
        coverage_rows.append(
            {
                "signal_date": pd.Timestamp(signal_date),
                "anchor_date": pd.Timestamp(anchor_date),
                "universe_n": int(len(members)),
                "signal_n": int(valid.sum()),
                "coverage": float(valid.sum() / len(members)),
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    return pd.DataFrame(rows), {
        "formation_sessions": FORMATION_SESSIONS,
        "signal_months": int(len(coverage)),
        "signal_rows": int(len(rows)),
        "coverage": _distribution(
            coverage["coverage"] if len(coverage) else pd.Series(dtype=float)
        ),
        "coverage_by_month": coverage.to_dict("records"),
    }


def _four_folds(monthly_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    monthly = pd.DataFrame(monthly_records)
    if monthly.empty:
        return []
    monthly["month"] = pd.to_datetime(monthly["month"], errors="raise")
    monthly = monthly.sort_values("month").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for number, positions in enumerate(np.array_split(np.arange(len(monthly)), 4), start=1):
        fold = monthly.iloc[positions]
        rows.append(
            {
                "fold": number,
                "start": fold["month"].min(),
                "end": fold["month"].max(),
                "months": int(len(fold)),
                "mean_ic": float(fold["ic"].mean()),
            }
        )
    return rows


def long_only_attribution(primary: dict[str, Any]) -> dict[str, float | None]:
    quintiles = primary["horizons"][PRIMARY_HORIZON]["quintiles"]
    means = quintiles.get("means", {})
    if not means or quintiles.get("q5_minus_all") is None:
        return {
            "past_loser_q5_mean": None,
            "past_winner_q1_mean": None,
            "investable_universe_mean": None,
            "long_leg_excess": None,
            "winner_short_leg_contribution": None,
            "long_short_spread": None,
            "winner_short_share_of_spread": None,
        }
    q1 = float(means["1"])
    q5 = float(means["5"])
    long_excess = float(quintiles["q5_minus_all"])
    universe = q5 - long_excess
    short_contribution = universe - q1
    spread = q5 - q1
    short_share = short_contribution / spread if spread != 0 else None
    return {
        "past_loser_q5_mean": q5,
        "past_winner_q1_mean": q1,
        "investable_universe_mean": universe,
        "long_leg_excess": long_excess,
        "winner_short_leg_contribution": short_contribution,
        "long_short_spread": spread,
        "winner_short_share_of_spread": short_share,
    }


def n20_exit_stress(
    events: pd.DataFrame, market_dates: pd.DatetimeIndex
) -> dict[str, Any]:
    """Treat path-ended and exceptionally delayed exits as total losses."""

    stressed = events.copy()
    missing = stressed["ret_20"].isna()
    right_censored = missing & stressed["entry_date"].gt(market_dates[-20])
    path_ended = missing & ~right_censored
    long_delay = stressed["exit_delay_20"].gt(FORMATION_SESSIONS)
    forced_loss = path_ended | long_delay
    stressed.loc[forced_loss, "ret_20"] = -1.0
    monthly = common._monthly_ic(stressed, "reversal_20", "ret_20")
    values = monthly["ic"].to_numpy(float) if len(monthly) else np.array([])
    return {
        "rule": (
            "ret_20=-100% for non-right-censored missing paths and exits delayed "
            "more than 20 ticker records"
        ),
        "path_ended_forced_loss": int(path_ended.sum()),
        "long_delay_forced_loss": int(long_delay.sum()),
        "forced_loss_events": int(forced_loss.sum()),
        "valid_months": int(len(monthly)),
        "hac": common._hac_mean(values),
        "block_bootstrap": common._block_bootstrap(values),
        "quintiles": common._quintiles(stressed, "reversal_20", "ret_20"),
    }


def _finite_ge(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) >= threshold


def _finite_gt(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > threshold


def evaluate_gates(
    primary: dict[str, Any], diagnostics: dict[str, Any]
) -> dict[str, Any]:
    n20 = primary["horizons"][PRIMARY_HORIZON]
    quintiles = n20["quintiles"]
    folds = _four_folds(n20["monthly"])
    attribution = long_only_attribution(primary)
    positive_folds = sum(fold["mean_ic"] > 0 for fold in folds)
    signal_data_gates = {
        "pit_universe_at_least_28_snapshots": diagnostics["universe_snapshots"] >= 28,
        "signal_coverage_min_ge_95pct": _finite_ge(
            diagnostics["signal_coverage"]["min"], MIN_COVERAGE
        ),
        "n20_at_least_60_valid_months": n20["valid_months"] >= MIN_SIGNAL_MONTHS,
        "historical_noncurrent_members_present": diagnostics["noncurrent_members"] > 0,
        "formation_uses_adjusted_close_only_through_signal_date": True,
    }
    signal_gates = {
        "n20_mean_ic_ge_003": _finite_ge(n20["hac"]["mean"], MIN_MEAN_IC),
        "n20_hac_t_ge_2": _finite_ge(n20["hac"]["t"], MIN_HAC_T),
        "n20_bootstrap_ci_above_zero": _finite_gt(
            n20["block_bootstrap"]["ci_low"], 0.0
        ),
        "n20_three_of_four_folds_positive": positive_folds >= 3,
        "n20_q5_minus_q1_positive_and_monotonic": (
            _finite_gt(quintiles["q5_minus_q1"], 0.0)
            and _finite_ge(quintiles["monotonic_rank_corr"], MIN_MONOTONICITY)
        ),
        "past_loser_q5_absolute_return_positive": _finite_gt(
            attribution["past_loser_q5_mean"], 0.0
        ),
        "long_only_q5_excess_ge_20bp_per_month": _finite_ge(
            attribution["long_leg_excess"], MIN_LONG_EXCESS
        ),
        "long_only_q5_excess_bootstrap_ci_above_zero": _finite_gt(
            quintiles["q5_excess_bootstrap"]["ci_low"], 0.0
        ),
    }
    signal_data_pass = all(signal_data_gates.values())
    signal_pass = all(signal_gates.values())
    execution_data_ready = False
    if not signal_data_pass:
        verdict = "DATA_NO_GO"
    elif not signal_pass:
        verdict = "SIGNAL_NO_GO"
    else:
        verdict = "RESEARCH_GO_EXECUTION_DATA_REQUIRED"
    return {
        "signal_data": signal_data_gates,
        "signal": signal_gates,
        "signal_data_pass": signal_data_pass,
        "signal_pass": signal_pass,
        "execution_data_ready": execution_data_ready,
        "verdict": verdict,
        "signal_probe_allowed": signal_data_pass,
        "cny_2_1m_portfolio_backtest_allowed": bool(
            signal_data_pass and signal_pass and execution_data_ready
        ),
        "four_folds": folds,
        "positive_fold_count": int(positive_folds),
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return pd.Timestamp(value).date().isoformat()
    if isinstance(value, np.generic):
        return _jsonable(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def run() -> dict[str, Any]:
    prices, close, _volume, _status = common._load_price_panels()
    universe, schedule = common.load_universe_schedule()
    signals, signal_diagnostics = build_reversal_signals(close, schedule)
    events = common.attach_forward_returns(signals, prices)
    primary = common.analyze_signal(events, "reversal_20")
    exposure = common.exposure_diagnostics(events, "reversal_20")

    market_dates = pd.DatetimeIndex(prices["date"].drop_duplicates().sort_values())
    exit_stress = n20_exit_stress(events, market_dates)
    n20_cutoff = market_dates[-20]
    n20_missing = events["ret_20"].isna()
    n20_right_censored = n20_missing & events["entry_date"].gt(n20_cutoff)
    member_counts = universe.groupby("as_of_date")["ticker"].nunique()
    current_members = schedule.members[-1]
    all_members = set(universe["ticker"].astype(str).str.upper())
    diagnostics = {
        "universe_snapshots": int(universe["as_of_date"].nunique()),
        "universe_member_count": _distribution(member_counts),
        "all_historical_members": int(len(all_members)),
        "latest_members": int(len(current_members)),
        "noncurrent_members": int(len(all_members - set(current_members))),
        "price_rows": int(len(prices)),
        "price_tickers": int(prices["ticker"].nunique()),
        "price_start": prices["date"].min(),
        "price_end": prices["date"].max(),
        "suspended_rows": int(prices["tradestatus"].eq(0).sum()),
        "signal_rows": int(len(signals)),
        "priced_events": int(len(events)),
        "signals_without_later_tradeable_entry": int(len(signals) - len(events)),
        "signal_coverage": signal_diagnostics["coverage"],
        "signal_coverage_by_month": signal_diagnostics["coverage_by_month"],
        "entry_delay_market_sessions": _distribution(events["entry_delay_market_sessions"]),
        "limit_up_events": int(events["limit_up"].sum()),
        "n20_missing": int(n20_missing.sum()),
        "n20_right_censored": int(n20_right_censored.sum()),
        "n20_path_ended_or_missing": int((n20_missing & ~n20_right_censored).sum()),
        "n20_delayed_exits": int(events["exit_delay_20"].gt(0).sum()),
        "n20_max_exit_delay_sessions": int(events["exit_delay_20"].dropna().max()),
        "pit_market_cap_coverage": float(events["pit_market_cap"].notna().mean()),
        "fresh_clone_rebuild_available": False,
        "historical_pit_industry_available": False,
        "nominal_ohlc_and_adjustment_factor_available": False,
        "historical_st_and_exact_limit_prices_available": False,
        "corporate_action_and_delist_ledger_available": False,
    }
    gates = evaluate_gates(primary, diagnostics)
    attribution = long_only_attribution(primary)
    payload = {
        "study": "A-share monthly 20-session short-term reversal first-look",
        "analysis_date": "2026-07-12",
        "capital_cny": 2_100_000,
        "protocol": {
            "candidate": "REV20 = -(adjusted_close_t / adjusted_close_t_minus_20 - 1)",
            "theory": (
                "Zhang and Zhu (2024) report strong short-horizon contrarian effects "
                "in China and attribute them to the T+1 mechanism; their abstract also "
                "states that the winner reversal dominates and both winner and loser "
                "portfolios can fall, so this test requires an independently profitable "
                "past-loser long leg"
            ),
            "paper": PAPER_DOI,
            "universe": "latest B070 PIT 800-member snapshot visible at each month-end",
            "formation": (
                "complete month-end close and the adjusted close exactly 20 market "
                "sessions earlier"
            ),
            "execution_label": (
                "first later tradestatus=1 open; N1 earliest legal T+1 close; N20/N60 "
                "first tradeable close at or after the frozen session target"
            ),
            "entry_limit_rule": (
                "freeze quintiles at signal date; inferred next-open limit-up names keep "
                "their intended long-only weight in cash and are not replaced"
            ),
            "primary_horizon": PRIMARY_HORIZON,
            "controls": ["N1", "N60"],
            "inference": (
                "monthly Spearman rank IC, Newey-West lag 3, circular 6-month block "
                "bootstrap with 5000 draws"
            ),
            "no_scan": [
                "formation window",
                "holding window",
                "Top-N or quantile cutoff",
                "February or holiday exclusion",
                "size or volatility neutralization",
            ],
            "contamination": (
                "C2-DIRECT: repository dates and related momentum/reversal results were "
                "previously inspected; any positive result is capped at paper candidate "
                "pending genuinely prospective evidence"
            ),
        },
        "input_evidence": {
            "prices": str(common.PRICE_PATH.relative_to(REPO_ROOT)),
            "prices_sha256": _sha256(common.PRICE_PATH),
            "universe": str(common.UNIVERSE_PATH.relative_to(REPO_ROOT)),
            "universe_sha256": _sha256(common.UNIVERSE_PATH),
            "size": str(common.SIZE_PATH.relative_to(REPO_ROOT)),
            "size_sha256": _sha256(common.SIZE_PATH),
            "runner_sha256": _sha256(Path(__file__)),
            "shared_helper": str(Path(common.__file__).relative_to(REPO_ROOT)),
            "shared_helper_sha256": _sha256(Path(common.__file__)),
            "test_sha256": _sha256(TEST_PATH) if TEST_PATH.is_file() else None,
        },
        "diagnostics": diagnostics,
        "primary": primary,
        "long_only_attribution": attribution,
        "n20_exit_stress": exit_stress,
        "exposure_diagnostics": exposure,
        "gates": gates,
        "interpretation_limits": [
            "This is a signal first-look, not a CNY 2.1m portfolio return backtest.",
            (
                "B070 is a liquid HS300/CSI500/SSE50-derived PIT subset, not the full "
                "A-share market; microcap reversal is not tested."
            ),
            (
                "Qfq OHLC is suitable for return labels but cannot certify 100-share "
                "lot sizing, historical capacity, or broker fills."
            ),
            (
                "Historical PIT industry, ST flags, exact exchange limit prices, "
                "corporate actions, and a delist cash ledger are unavailable."
            ),
            (
                "The input caches are gitignored; hashes identify this run but a fresh "
                "clone cannot rebuild it."
            ),
            (
                "A long-short spread is not implementable evidence when its profit is "
                "concentrated in shorting past winners."
            ),
            (
                "Signals with no later tradeable entry are absent from the shared event "
                "labeler rather than retained as cash; the count is disclosed."
            ),
            "No broker, paper account, product strategy, or production configuration was touched.",
        ],
    }
    return _jsonable(payload)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(list(argv) if argv is not None else None)
    payload = run()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["gates"], indent=2, sort_keys=True))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
