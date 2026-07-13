#!/usr/bin/env python
"""Independent A-share low-MAX lottery-avoidance first-look.

The evaluator-only runner tests whether avoiding stocks with an extreme positive
daily return in the prior 20 market sessions produces a buyable N20 long leg in
the B070 point-in-time universe.  Raw low-MAX and a preregistered residual low-MAX
signal must both pass.  The residual removes contemporaneous realized volatility,
PIT circulating size, and trailing return ranks so that generic low-vol, size, or
the already-rejected short-term reversal exposure cannot masquerade as new alpha.

This module does not call or modify any product strategy or portfolio engine.
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
from scripts.test import ashare_short_term_reversal_first_look as reversal_common

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = (
    REPO_ROOT / "docs" / "test-reports" / "ashare-low-max-first-look-2026-07-12.json"
)
TEST_PATH = REPO_ROOT / "tests" / "unit" / "test_ashare_low_max_first_look.py"
PAPER_DOIS = (
    "https://doi.org/10.1016/j.jfineco.2010.08.014",
    "https://doi.org/10.1016/j.jbankfin.2016.12.008",
    "https://doi.org/10.1016/j.jfineco.2019.03.008",
    "https://doi.org/10.1016/j.iref.2017.10.015",
    "https://doi.org/10.1080/23322039.2023.2175471",
    "https://doi.org/10.1016/j.pacfin.2022.101852",
)
FORMATION_SESSIONS = 20
MIN_CROSS_SECTION = 100
MIN_SIGNAL_MONTHS = 60
MIN_COVERAGE = 0.95
MIN_MEAN_IC = 0.03
MIN_HAC_T = 2.0
MIN_LONG_EXCESS = 0.002
MIN_MONOTONICITY = 0.70
MAX_RESIDUAL_EXPOSURE_GAP = 0.10


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pit_value(
    history: tuple[np.ndarray, np.ndarray] | None, timestamp: pd.Timestamp
) -> float:
    if history is None:
        return np.nan
    dates, values = history
    position = int(np.searchsorted(dates, np.datetime64(timestamp), side="right")) - 1
    return float(values[position]) if position >= 0 else np.nan


def build_lowmax_signals(
    close: pd.DataFrame,
    status: pd.DataFrame,
    schedule: common.UniverseSchedule,
    *,
    size_path: Path = common.SIZE_PATH,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build raw and residual low-MAX scores using only formation-date inputs."""

    if not close.index.equals(status.index) or not close.columns.equals(status.columns):
        raise ValueError("close and status panels must share index and columns")
    ordered = close.sort_index()
    ordered_status = status.reindex(index=ordered.index, columns=ordered.columns)
    month_ends = common._complete_month_end_dates(ordered.index)
    size_histories = common._size_histories(size_path)
    rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    orthogonality_rows: list[dict[str, Any]] = []
    for signal_date in month_ends:
        position = int(ordered.index.get_indexer([signal_date])[0])
        if position < FORMATION_SESSIONS:
            continue
        members = sorted(schedule.members_on(signal_date))
        if len(members) < MIN_CROSS_SECTION:
            continue
        available = [ticker for ticker in members if ticker in ordered.columns]
        window = ordered.iloc[position - FORMATION_SESSIONS : position + 1][available]
        status_window = ordered_status.iloc[
            position - FORMATION_SESSIONS : position + 1
        ][available]
        daily_returns = window.pct_change(fill_method=None).iloc[1:]
        daily_returns = daily_returns.mask(status_window.iloc[1:].eq(0), 0.0)
        valid_price = (
            window.notna().all()
            & window.gt(0).all()
            & status_window.notna().all()
            & daily_returns.notna().all()
            & np.isfinite(daily_returns).all()
        )
        max20 = daily_returns.max().where(valid_price)
        rvol20 = daily_returns.std(ddof=1).mul(math.sqrt(252)).where(valid_price)
        ret20 = daily_returns.add(1.0).prod().sub(1.0).where(valid_price)
        market_cap = pd.Series(
            {
                ticker: _pit_value(size_histories.get(ticker), signal_date)
                for ticker in available
            },
            dtype=float,
        )
        frame = pd.DataFrame(
            {
                "max20": max20,
                "rvol20": rvol20,
                "past_return_20": ret20,
                "pit_market_cap_signal": market_cap,
            }
        ).replace([np.inf, -np.inf], np.nan)
        frame = frame.dropna()
        frame = frame[frame["pit_market_cap_signal"].gt(0)]
        if len(frame) < MIN_CROSS_SECTION:
            continue
        frame["log_mcap"] = np.log(frame["pit_market_cap_signal"])
        for column in ("max20", "rvol20", "log_mcap", "past_return_20"):
            frame[f"{column}_rank"] = frame[column].rank(method="average", pct=True)
        design = np.column_stack(
            [
                np.ones(len(frame)),
                frame["rvol20_rank"].to_numpy(float),
                frame["log_mcap_rank"].to_numpy(float),
                frame["past_return_20_rank"].to_numpy(float),
            ]
        )
        outcome = frame["max20_rank"].to_numpy(float)
        coefficients, *_ = np.linalg.lstsq(design, outcome, rcond=None)
        frame["max20_rank_residual"] = outcome - design @ coefficients
        frame["raw_lowmax"] = -frame["max20"]
        frame["residual_lowmax"] = -frame["max20_rank_residual"]
        frame["lowvol_control"] = -frame["rvol20"]
        frame["reversal_control"] = -frame["past_return_20"]
        for ticker, values in frame.iterrows():
            rows.append(
                {
                    "signal_date": pd.Timestamp(signal_date),
                    "ticker": str(ticker),
                    **{column: float(values[column]) for column in frame.columns},
                }
            )
        correlations = {
            control: float(frame["residual_lowmax"].corr(frame[control]))
            for control in (
                "rvol20_rank",
                "log_mcap_rank",
                "past_return_20_rank",
            )
        }
        orthogonality_rows.append(
            {
                "signal_date": pd.Timestamp(signal_date),
                **correlations,
                "design_rank": int(np.linalg.matrix_rank(design)),
            }
        )
        coverage_rows.append(
            {
                "signal_date": pd.Timestamp(signal_date),
                "anchor_date": pd.Timestamp(window.index[0]),
                "universe_n": int(len(members)),
                "signal_n": int(len(frame)),
                "coverage": float(len(frame) / len(members)),
            }
        )
    coverage = pd.DataFrame(coverage_rows)
    orthogonality = pd.DataFrame(orthogonality_rows)
    corr_columns = ("rvol20_rank", "log_mcap_rank", "past_return_20_rank")
    max_abs_correlation = (
        float(orthogonality[list(corr_columns)].abs().to_numpy().max())
        if len(orthogonality)
        else None
    )
    return pd.DataFrame(rows), {
        "formation_sessions": FORMATION_SESSIONS,
        "signal_months": int(len(coverage)),
        "signal_rows": int(len(rows)),
        "coverage": reversal_common._distribution(
            coverage["coverage"] if len(coverage) else pd.Series(dtype=float)
        ),
        "coverage_by_month": coverage.to_dict("records"),
        "residual_control_correlations_by_month": orthogonality.to_dict("records"),
        "residual_max_abs_control_correlation": max_abs_correlation,
        "residual_design_full_rank_months": (
            int(orthogonality["design_rank"].eq(4).sum()) if len(orthogonality) else 0
        ),
    }


def retain_no_entry_as_cash(signals: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Retain signals with no later tradeable open as frozen cash slots."""

    event_keys = events[["signal_date", "ticker"]].copy()
    missing = signals.merge(
        event_keys.assign(_priced=True),
        on=["signal_date", "ticker"],
        how="left",
        validate="one_to_one",
    )
    missing = missing[missing["_priced"].isna()].drop(columns="_priced")
    priced = events.copy()
    priced["no_tradeable_entry"] = False
    if missing.empty:
        return priced
    cash = missing.copy()
    cash["entry_date"] = pd.NaT
    cash["entry_delay_market_sessions"] = np.nan
    cash["entry_open_return"] = np.nan
    cash["limit_up"] = True
    cash["no_tradeable_entry"] = True
    cash["pre20_return"] = cash["past_return_20"]
    cash["pre60_volatility"] = np.nan
    cash["pre20_median_amount_proxy"] = np.nan
    cash["pit_market_cap"] = cash["pit_market_cap_signal"]
    for horizon in common.HORIZONS:
        cash[f"ret_{horizon}"] = 0.0
        cash[f"exit_delay_{horizon}"] = np.nan
    return pd.concat([priced, cash], ignore_index=True, sort=False)


def signal_exposure_diagnostics(events: pd.DataFrame, signal: str) -> dict[str, Any]:
    frame = events.dropna(
        subset=[signal, "rvol20_rank", "log_mcap_rank", "past_return_20_rank"]
    ).copy()
    rows: list[dict[str, Any]] = []
    for month, cohort in frame.groupby("signal_date", sort=True):
        ranks = cohort[signal].rank(method="average", pct=True)
        quintile = np.ceil(ranks * 5).clip(1, 5).astype(int)
        top = cohort.loc[quintile.eq(5)]
        if top.empty:
            continue
        rows.append(
            {
                "month": pd.Timestamp(month),
                "rvol_rank_gap": float(
                    top["rvol20_rank"].mean() - cohort["rvol20_rank"].mean()
                ),
                "log_mcap_rank_gap": float(
                    top["log_mcap_rank"].mean() - cohort["log_mcap_rank"].mean()
                ),
                "past_return_rank_gap": float(
                    top["past_return_20_rank"].mean()
                    - cohort["past_return_20_rank"].mean()
                ),
            }
        )
    table = pd.DataFrame(rows)
    if table.empty:
        return {
            "months": 0,
            "mean_rvol_rank_gap": None,
            "mean_log_mcap_rank_gap": None,
            "mean_past_return_rank_gap": None,
        }
    return {
        "months": int(len(table)),
        "mean_rvol_rank_gap": float(table["rvol_rank_gap"].mean()),
        "mean_log_mcap_rank_gap": float(table["log_mcap_rank_gap"].mean()),
        "mean_past_return_rank_gap": float(table["past_return_rank_gap"].mean()),
        "by_month": table.to_dict("records"),
    }


def n20_exit_stress(
    events: pd.DataFrame, market_dates: pd.DatetimeIndex, signal: str
) -> dict[str, Any]:
    stressed = events.copy()
    missing = stressed["ret_20"].isna()
    right_censored = missing & stressed["entry_date"].gt(market_dates[-20])
    path_ended = missing & ~right_censored
    long_delay = stressed["exit_delay_20"].gt(FORMATION_SESSIONS)
    forced_loss = path_ended | long_delay
    stressed.loc[forced_loss, "ret_20"] = -1.0
    monthly = common._monthly_ic(stressed, signal, "ret_20")
    values = monthly["ic"].to_numpy(float) if len(monthly) else np.array([])
    return {
        "signal": signal,
        "path_ended_forced_loss": int(path_ended.sum()),
        "long_delay_forced_loss": int(long_delay.sum()),
        "forced_loss_events": int(forced_loss.sum()),
        "valid_months": int(len(monthly)),
        "hac": common._hac_mean(values),
        "block_bootstrap": common._block_bootstrap(values),
        "quintiles": common._quintiles(stressed, signal, "ret_20"),
    }


def _finite_ge(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) >= threshold


def _finite_gt(value: Any, threshold: float) -> bool:
    return value is not None and math.isfinite(float(value)) and float(value) > threshold


def signal_gates(analysis: dict[str, Any]) -> dict[str, bool]:
    n20 = analysis["horizons"]["N20"]
    quintiles = n20["quintiles"]
    attribution = reversal_common.long_only_attribution(analysis)
    folds = reversal_common._four_folds(n20["monthly"])
    positive_folds = sum(fold["mean_ic"] > 0 for fold in folds)
    return {
        "n20_mean_ic_ge_003": _finite_ge(n20["hac"]["mean"], MIN_MEAN_IC),
        "n20_hac_t_ge_2": _finite_ge(n20["hac"]["t"], MIN_HAC_T),
        "n20_ic_bootstrap_ci_above_zero": _finite_gt(
            n20["block_bootstrap"]["ci_low"], 0.0
        ),
        "n20_three_of_four_folds_positive": positive_folds >= 3,
        "n20_q5_minus_q1_positive_and_monotonic": (
            _finite_gt(quintiles["q5_minus_q1"], 0.0)
            and _finite_ge(quintiles["monotonic_rank_corr"], MIN_MONOTONICITY)
        ),
        "q5_absolute_return_positive": _finite_gt(
            attribution["past_loser_q5_mean"], 0.0
        ),
        "q5_excess_ge_20bp_per_month": _finite_ge(
            attribution["long_leg_excess"], MIN_LONG_EXCESS
        ),
        "q5_excess_hac_t_ge_2": _finite_ge(
            quintiles["q5_excess_hac"]["t"], MIN_HAC_T
        ),
        "q5_excess_bootstrap_ci_above_zero": _finite_gt(
            quintiles["q5_excess_bootstrap"]["ci_low"], 0.0
        ),
    }


def evaluate_gates(
    raw: dict[str, Any],
    residual: dict[str, Any],
    diagnostics: dict[str, Any],
    residual_exposure: dict[str, Any],
) -> dict[str, Any]:
    raw_n20 = raw["horizons"]["N20"]
    residual_n20 = residual["horizons"]["N20"]
    data_gates = {
        "pit_universe_at_least_28_snapshots": diagnostics["universe_snapshots"] >= 28,
        "historical_noncurrent_members_present": diagnostics["noncurrent_members"] > 0,
        "signal_coverage_min_ge_95pct": _finite_ge(
            diagnostics["signal_coverage"]["min"], MIN_COVERAGE
        ),
        "raw_and_residual_n20_at_least_60_months": (
            min(raw_n20["valid_months"], residual_n20["valid_months"])
            >= MIN_SIGNAL_MONTHS
        ),
        "residual_design_full_rank_each_month": (
            diagnostics["residual_design_full_rank_months"]
            == diagnostics["signal_months"]
        ),
        "formation_inputs_not_after_signal_date": True,
    }
    raw_checks = signal_gates(raw)
    residual_checks = signal_gates(residual)
    attribution_checks = {
        "residual_controls_numerically_orthogonal": _finite_ge(
            1e-10, diagnostics["residual_max_abs_control_correlation"]
        ),
        "residual_q5_rvol_rank_gap_abs_le_010": (
            residual_exposure["mean_rvol_rank_gap"] is not None
            and abs(float(residual_exposure["mean_rvol_rank_gap"]))
            <= MAX_RESIDUAL_EXPOSURE_GAP
        ),
        "residual_q5_size_rank_gap_abs_le_010": (
            residual_exposure["mean_log_mcap_rank_gap"] is not None
            and abs(float(residual_exposure["mean_log_mcap_rank_gap"]))
            <= MAX_RESIDUAL_EXPOSURE_GAP
        ),
    }
    data_pass = all(data_gates.values())
    signal_pass = all(raw_checks.values()) and all(residual_checks.values())
    attribution_pass = all(attribution_checks.values())
    execution_data_ready = False
    if not data_pass:
        verdict = "DATA_NO_GO"
    elif not signal_pass or not attribution_pass:
        verdict = "SIGNAL_NO_GO"
    else:
        verdict = "RESEARCH_GO_EXECUTION_DATA_REQUIRED"
    return {
        "data": data_gates,
        "raw_lowmax": raw_checks,
        "residual_lowmax": residual_checks,
        "attribution": attribution_checks,
        "data_pass": data_pass,
        "raw_signal_pass": all(raw_checks.values()),
        "residual_signal_pass": all(residual_checks.values()),
        "attribution_pass": attribution_pass,
        "signal_pass": bool(signal_pass and attribution_pass),
        "execution_data_ready": execution_data_ready,
        "verdict": verdict,
        "cny_2_1m_portfolio_backtest_allowed": bool(
            data_pass and signal_pass and attribution_pass and execution_data_ready
        ),
        "raw_four_folds": reversal_common._four_folds(raw_n20["monthly"]),
        "residual_four_folds": reversal_common._four_folds(residual_n20["monthly"]),
    }


def run() -> dict[str, Any]:
    prices, close, _volume, status = common._load_price_panels()
    universe, schedule = common.load_universe_schedule()
    signals, signal_diagnostics = build_lowmax_signals(close, status, schedule)
    priced_events = common.attach_forward_returns(signals, prices)
    events = retain_no_entry_as_cash(signals, priced_events)

    raw = common.analyze_signal(events, "raw_lowmax")
    residual = common.analyze_signal(events, "residual_lowmax")
    lowvol = common.analyze_signal(events, "lowvol_control")
    reversal = common.analyze_signal(events, "reversal_control")
    raw_exposure = signal_exposure_diagnostics(events, "raw_lowmax")
    residual_exposure = signal_exposure_diagnostics(events, "residual_lowmax")
    market_dates = pd.DatetimeIndex(prices["date"].drop_duplicates().sort_values())
    raw_stress = n20_exit_stress(events, market_dates, "raw_lowmax")
    residual_stress = n20_exit_stress(events, market_dates, "residual_lowmax")

    member_counts = universe.groupby("as_of_date")["ticker"].nunique()
    all_members = set(universe["ticker"].astype(str).str.upper())
    latest_members = set(schedule.members[-1])
    n20_missing = events["ret_20"].isna()
    n20_right_censored = n20_missing & events["entry_date"].gt(market_dates[-20])
    raw_close_returns = close.pct_change(fill_method=None)
    suspended_close_returns = status.eq(0) & raw_close_returns.notna()
    diagnostics = {
        "universe_snapshots": int(universe["as_of_date"].nunique()),
        "universe_member_count": reversal_common._distribution(member_counts),
        "all_historical_members": int(len(all_members)),
        "latest_members": int(len(latest_members)),
        "noncurrent_members": int(len(all_members - latest_members)),
        "price_rows": int(len(prices)),
        "price_tickers": int(prices["ticker"].nunique()),
        "price_start": prices["date"].min(),
        "price_end": prices["date"].max(),
        "suspended_rows": int(prices["tradestatus"].eq(0).sum()),
        "nonzero_suspended_close_returns_forced_zero": int(
            (suspended_close_returns & raw_close_returns.abs().gt(1e-15))
            .to_numpy()
            .sum()
        ),
        "signal_months": signal_diagnostics["signal_months"],
        "signal_rows": int(len(signals)),
        "priced_events": int(len(priced_events)),
        "events_including_no_entry_cash": int(len(events)),
        "signals_without_later_tradeable_entry": int(events["no_tradeable_entry"].sum()),
        "signal_coverage": signal_diagnostics["coverage"],
        "signal_coverage_by_month": signal_diagnostics["coverage_by_month"],
        "residual_design_full_rank_months": signal_diagnostics[
            "residual_design_full_rank_months"
        ],
        "residual_max_abs_control_correlation": signal_diagnostics[
            "residual_max_abs_control_correlation"
        ],
        "residual_control_correlations_by_month": signal_diagnostics[
            "residual_control_correlations_by_month"
        ],
        "limit_up_or_no_entry_cash_events": int(events["limit_up"].sum()),
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
    gates = evaluate_gates(raw, residual, diagnostics, residual_exposure)
    payload = {
        "study": "A-share low-MAX lottery-avoidance first-look",
        "analysis_date": "2026-07-12",
        "capital_cny": 2_100_000,
        "protocol": {
            "raw_signal": (
                "raw_lowmax = -max(adjusted close-to-close return over the final "
                "20 market sessions through each complete month-end)"
            ),
            "suspension_rule": (
                "carried qfq close on a suspended market session contributes a zero "
                "daily return; the window is not extended to 20 tradeable ticker days"
            ),
            "residual_signal": (
                "monthly percentile-rank MAX20 regressed on percentile-rank RVOL20, "
                "log PIT circulating market cap, and RET20; signal is negative residual"
            ),
            "theory_sources": list(PAPER_DOIS),
            "universe": "latest B070 PIT 800-member snapshot visible at each month-end",
            "execution_label": (
                "first later tradestatus=1 open; N1 earliest legal T+1 close; N20/N60 "
                "first tradeable close at or after the entry-inclusive target"
            ),
            "entry_cash_rule": (
                "freeze quintiles before execution; inferred limit-up and no-later-entry "
                "slots earn zero cash return and are not replaced"
            ),
            "primary_horizon": "N20",
            "controls": ["N1", "N60", "lowvol_control", "reversal_control"],
            "inference": (
                "monthly Spearman rank IC, Newey-West lag 3, circular 6-month block "
                "bootstrap with 5000 draws"
            ),
            "no_scan": [
                "formation or holding window",
                "Top-N or quantile cutoff",
                "special-month exclusion",
                "residual controls or regression form",
            ],
            "contamination": (
                "C2-DIRECT: the same B070 future-return dates have been inspected in "
                "prior trials; a positive result is capped at a paper candidate pending "
                "genuinely prospective evidence"
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
            "shared_helpers": [
                str(Path(common.__file__).relative_to(REPO_ROOT)),
                str(Path(reversal_common.__file__).relative_to(REPO_ROOT)),
            ],
            "shared_helper_sha256": [
                _sha256(Path(common.__file__)),
                _sha256(Path(reversal_common.__file__)),
            ],
            "test_sha256": _sha256(TEST_PATH) if TEST_PATH.is_file() else None,
        },
        "diagnostics": diagnostics,
        "raw_lowmax": raw,
        "residual_lowmax": residual,
        "controls": {
            "lowvol": lowvol,
            "reversal": reversal,
            "raw_minus_lowvol_n20_ic": common.compare_monthly_ic(raw, lowvol),
            "raw_minus_reversal_n20_ic": common.compare_monthly_ic(raw, reversal),
        },
        "long_only_attribution": {
            "raw": reversal_common.long_only_attribution(raw),
            "residual": reversal_common.long_only_attribution(residual),
        },
        "exposure_diagnostics": {
            "raw": raw_exposure,
            "residual": residual_exposure,
            "industry_neutrality": (
                "not testable: historical PIT industry labels are unavailable"
            ),
        },
        "n20_exit_stress": {"raw": raw_stress, "residual": residual_stress},
        "gates": gates,
        "interpretation_limits": [
            "This is a signal first-look, not a CNY 2.1m portfolio return backtest.",
            (
                "B070 is a liquid HS300/CSI500/SSE50-derived PIT subset, not the full "
                "A-share market; a microcap-concentrated MAX effect may be absent."
            ),
            (
                "B076 is inferred PIT circulating market cap, adequate for exposure "
                "control but not total-market-cap or execution-capacity certification."
            ),
            (
                "Qfq OHLC lacks nominal prices, adjustment factors, historical ST and "
                "exact limit prices, corporate actions, and a delist cash ledger."
            ),
            (
                "Input caches are gitignored; hashes identify this run but a fresh clone "
                "cannot rebuild it."
            ),
            (
                "No broker, paper account, product strategy, or production configuration "
                "was touched."
            ),
        ],
    }
    return reversal_common._jsonable(payload)


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
