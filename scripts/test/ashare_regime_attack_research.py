#!/usr/bin/env python
"""Independent E0/E1/E2 research on the de-biased A-share attack strategy.

This evaluator-owned runner does not modify production strategy code. It reuses the
existing CN attack engine and temporarily gates its signal function for E2:

* E0: 1M CNY, pure momentum, equal weight, full fidelity, aggregate 20% band.
* E1: E0 plus the existing 0.5% per-name partial-rebalance research switch.
* E2: E0 plus a monthly CSI300 close > 200-day moving-average risk gate. Risk-off
  returns an empty target, so the production engine handles the T+1 liquidation,
  costs, round lots, halts, delistings, and price-limit restrictions unchanged.

The historical window has already been inspected by prior batches. Positive results
are therefore research evidence only and can at most qualify a candidate for paper
forward validation; negative results can still reject a candidate.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import subprocess
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
B070_ROOT = REPO_ROOT / "data/research/b070"
PRICES_PATH = B070_ROOT / "b081_prices_cache.pkl"
UNIVERSE_PATH = B070_ROOT / "snapshots/universe/cn_pit_universe.csv"
HS300_PATH = REPO_ROOT / "data/research/b082/hs300.csv"
HS300_CONTROL_PATH = (
    REPO_ROOT / "data/research/b068/snapshots/benchmark/cn_csi300.csv"
)
DEFAULT_OUTPUT = (
    REPO_ROOT / "docs/test-reports/ashare-regime-attack-research-2026-07-11.json"
)
DEFAULT_CACHE_DIR = B070_ROOT / "codex_regime_research_cache"

START = date(2019, 4, 1)
STARTING_CAPITAL = 1_000_000.0
IN_SAMPLE_FRACTION = 0.70
MA_DAYS = 200
BLOCK_MONTHS = 6
BOOTSTRAP_SAMPLES = 10_000
BOOTSTRAP_SEED = 20_260_711
CACHE_VERSION = "ashare-regime-v2"

PRIMARY_COST_BPS = {
    "stamp_duty_bps": 5.0,
    "commission_bps": 2.5,
    "slippage_bps": 5.0,
}

VERDICT_GATES = {
    "min_delta_cagr": 0.02,
    "min_delta_sharpe": 0.15,
    "max_drawdown_floor": -0.35,
    "min_positive_folds": 2,
    "max_2024q4_improvement_share": 0.50,
}

FOLDS = (
    ("2019-2021", date(2019, 4, 1), date(2021, 12, 31)),
    ("2022-2023", date(2022, 1, 1), date(2023, 12, 31)),
    ("2024-2026", date(2024, 1, 1), date(2026, 6, 18)),
)

STRESS_WINDOWS = (
    ("2022", date(2022, 1, 1), date(2022, 12, 31)),
    ("2024_jan_feb", date(2024, 1, 1), date(2024, 2, 29)),
    ("2024_924_q4", date(2024, 9, 24), date(2024, 12, 31)),
)


@dataclass(frozen=True, slots=True)
class RegimeSchedule:
    """Monthly CSI300 regime states with explicit source dates."""

    states: pd.Series

    def state_on(self, as_of_date: date) -> bool:
        timestamp = pd.Timestamp(as_of_date)
        position = int(self.states.index.searchsorted(timestamp, side="right")) - 1
        if position < 0:
            raise ValueError(f"no completed monthly regime state for {as_of_date}")
        return bool(self.states.iloc[position])

    def source_date_on(self, as_of_date: date) -> date:
        timestamp = pd.Timestamp(as_of_date)
        position = int(self.states.index.searchsorted(timestamp, side="right")) - 1
        if position < 0:
            raise ValueError(f"no completed monthly regime source for {as_of_date}")
        return pd.Timestamp(self.states.index[position]).date()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()


def _build_regime_schedule(hs300: pd.DataFrame) -> RegimeSchedule:
    frame = hs300.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    if frame.empty or frame["close"].isna().any():
        raise ValueError("CSI300 data must be non-empty with complete closes")
    frame["ma200"] = frame["close"].rolling(MA_DAYS, min_periods=MA_DAYS).mean()
    month_end = frame.groupby(frame["date"].dt.to_period("M"), sort=True).tail(1)
    month_end = month_end.dropna(subset=["ma200"])
    states = (month_end.set_index("date")["close"] > month_end.set_index("date")["ma200"])
    states.index = pd.DatetimeIndex(states.index)
    states = states.astype(bool).sort_index()
    if states.empty or not states.index.is_monotonic_increasing:
        raise ValueError("failed to build monotonic monthly CSI300 regime schedule")
    return RegimeSchedule(states=states)


@contextlib.contextmanager
def _regime_signal_gate(
    schedule: RegimeSchedule,
) -> Iterator[dict[str, int]]:
    """Temporarily replace the engine's signal with a monthly risk gate."""

    from trade.backtest.cn_attack_momentum_quality import engine as engine_module
    from trade.strategies.cn_attack_momentum_quality.construction import (
        CnPortfolioWeights,
    )
    from trade.strategies.cn_attack_momentum_quality.signal import CnSignalResult

    original = engine_module.generate_cn_attack_signal
    original_turnover = engine_module._would_be_turnover
    force_cash = {"active": False}
    counters = {
        "risk_on_calls": 0,
        "risk_off_calls": 0,
        "forced_cash_retry_calls": 0,
    }

    def gated_signal(
        parameters: Any,
        as_of_date: date,
        current_holdings: Mapping[str, float] | None = None,
        **kwargs: Any,
    ) -> Any:
        if schedule.source_date_on(as_of_date) > as_of_date:
            raise AssertionError("regime source date is after the signal date")
        if schedule.state_on(as_of_date):
            force_cash["active"] = False
            counters["risk_on_calls"] += 1
            return original(parameters, as_of_date, current_holdings, **kwargs)
        force_cash["active"] = True
        counters["risk_off_calls"] += 1
        members = kwargs.get("universe_members") or ()
        return CnSignalResult(
            as_of_date=as_of_date,
            parameters_hash=parameters.parameter_hash(),
            factor_variant=parameters.factor_variant,
            universe_size=len(members),
            portfolio=CnPortfolioWeights(weights=(), cash_buffer=1.0),
            factor_contributions=(),
        )

    def gated_turnover(
        current_weights: Mapping[str, float], target: Mapping[str, float]
    ) -> float:
        value = original_turnover(current_weights, target)
        if force_cash["active"] and current_weights and not target and value <= 0.20:
            counters["forced_cash_retry_calls"] += 1
            return 0.200000001
        return value

    engine_module.generate_cn_attack_signal = gated_signal
    engine_module._would_be_turnover = gated_turnover
    try:
        yield counters
    finally:
        engine_module.generate_cn_attack_signal = original
        engine_module._would_be_turnover = original_turnover


@contextlib.contextmanager
def _trade_status_real_bar_mask() -> Iterator[None]:
    """Use Baostock ``tradestatus`` instead of non-null adjusted close for halts.

    The shipped B081 mask treats a frozen, carried price as a real trading bar. This
    evaluator-only sensitivity patch keeps production code untouched while testing
    the data source's documented ``tradestatus == 1`` execution semantics.
    """

    from trade.backtest.cn_attack_momentum_quality import engine as engine_module

    original = engine_module._real_bar_mask

    def corrected(prices: pd.DataFrame) -> pd.DataFrame:
        if "tradestatus" not in prices.columns:
            raise ValueError("corrected halt mask requires tradestatus")
        return (
            prices.pivot_table(
                index="date",
                columns="ticker",
                values="tradestatus",
                aggfunc="last",
            )
            .sort_index()
            .fillna(0)
            .eq(1)
        )

    engine_module._real_bar_mask = corrected
    try:
        yield
    finally:
        engine_module._real_bar_mask = original


def _cost_model(multiplier: float) -> Any:
    from trade.backtest.cn_attack_momentum_quality.costs import CnCostModel

    return CnCostModel(
        stamp_duty_bps=PRIMARY_COST_BPS["stamp_duty_bps"] * multiplier,
        commission_bps=PRIMARY_COST_BPS["commission_bps"] * multiplier,
        slippage_bps=PRIMARY_COST_BPS["slippage_bps"] * multiplier,
    )


def _parameters() -> Any:
    from trade.strategies.cn_attack_momentum_quality.parameters import (
        FACTOR_VARIANT_PURE_MOMENTUM,
        WEIGHTING_SCHEME_EQUAL,
        CnAttackParameters,
    )

    return CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM,
        weighting_scheme=WEIGHTING_SCHEME_EQUAL,
    )


def _config(*, partial_rebalance: bool, cost_multiplier: float) -> Any:
    from trade.backtest.cn_attack_momentum_quality.engine import CnAttackBacktestConfig

    return CnAttackBacktestConfig(
        starting_capital=STARTING_CAPITAL,
        cost_model=_cost_model(cost_multiplier),
        no_trade_band=0.20,
        lot_rounding=True,
        partial_rebalance=partial_rebalance,
        per_name_rebalance_threshold=0.005,
        suspension_halt=True,
        delist_liquidation=True,
        delist_recovery_rate=1.0,
        price_limit_gating=True,
    )


def _run_variant(
    *,
    prices: pd.DataFrame,
    universe_history: Any,
    schedule: RegimeSchedule,
    partial_rebalance: bool,
    use_regime_gate: bool,
    corrected_halt_mask: bool,
    cost_multiplier: float,
) -> dict[str, Any]:
    from trade.backtest.cn_attack_momentum_quality import engine as engine_module

    counters = {"risk_on_calls": 0, "risk_off_calls": 0}

    def execute() -> Any:
        return engine_module.run_cn_attack_backtest(
            _parameters(),
            _config(
                partial_rebalance=partial_rebalance,
                cost_multiplier=cost_multiplier,
            ),
            START,
            None,
            prices=prices,
            universe_history=universe_history,
        )

    with contextlib.ExitStack() as stack:
        if corrected_halt_mask:
            stack.enter_context(_trade_status_real_bar_mask())
        live_counters = (
            stack.enter_context(_regime_signal_gate(schedule))
            if use_regime_gate
            else None
        )
        result = execute()
        if live_counters is not None:
            counters = dict(live_counters)

    return {
        "equity_curve": result.equity_curve,
        "total_turnover": float(result.total_turnover),
        "total_cost": float(result.total_cost),
        "rebalance_count": int(result.rebalance_count),
        "exit_count": int(result.exit_count),
        "trading_days": int(result.trading_days),
        "regime_calls": counters,
        "regime_transition_evidence": (
            _transition_evidence(result.daily_records, schedule)
            if use_regime_gate
            else []
        ),
        "final_cash_weight": float(result.final_holdings.cash_weight),
        "final_holding_count": int(len(result.final_holdings.weights)),
    }


def _transition_evidence(records: Any, schedule: RegimeSchedule) -> list[dict[str, Any]]:
    record_list = list(records)
    by_date = {record.date: (index, record) for index, record in enumerate(record_list)}
    changed = schedule.states.loc[schedule.states.astype(int).diff().abs() == 1]
    evidence: list[dict[str, Any]] = []
    for timestamp, state in changed.items():
        signal_date = pd.Timestamp(timestamp).date()
        located = by_date.get(signal_date)
        if located is None or signal_date < START:
            continue
        index, record = located
        execution = None
        for later in record_list[index + 1 : index + 8]:
            if later.executed_turnover > 0.0:
                execution = {
                    "date": str(later.date),
                    "turnover": float(later.executed_turnover),
                    "cost": float(later.executed_cost),
                }
                break
        evidence.append(
            {
                "signal_date": str(signal_date),
                "risk_on": bool(state),
                "decision_rebalanced": bool(record.rebalanced),
                "target_count": int(len(record.target_tickers)),
                "first_execution_within_7_days": execution,
            }
        )
    return evidence


def _period_curve(curve: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    dates = pd.to_datetime(curve["date"])
    selected = curve.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))].copy()
    return selected.reset_index(drop=True)


def _drawdown_details(curve: pd.DataFrame) -> dict[str, Any]:
    if curve.empty:
        return {"max_drawdown": 0.0, "peak_date": None, "trough_date": None}
    values = curve["equity"].astype(float).reset_index(drop=True)
    dates = pd.to_datetime(curve["date"]).reset_index(drop=True)
    peaks = values.cummax()
    drawdowns = values / peaks - 1.0
    trough_index = int(drawdowns.idxmin())
    peak_index = int(values.iloc[: trough_index + 1].idxmax())
    recovery = None
    peak_value = float(values.iloc[peak_index])
    for index in range(trough_index + 1, len(values)):
        if float(values.iloc[index]) >= peak_value:
            recovery = str(dates.iloc[index].date())
            break
    return {
        "max_drawdown": float(drawdowns.iloc[trough_index]),
        "peak_date": str(dates.iloc[peak_index].date()),
        "trough_date": str(dates.iloc[trough_index].date()),
        "recovery_date": recovery,
    }


def _metrics(
    curve: pd.DataFrame,
    *,
    turnover: float,
    total_cost: float,
    rebalance_count: int,
    exit_count: int,
) -> dict[str, Any]:
    from trade.backtest.us_quality_momentum.metrics import (
        annualized_return,
        annualized_volatility,
        calmar_ratio,
        max_drawdown,
        sharpe_ratio,
        sortino_ratio,
    )

    clean = curve.copy()
    clean["date"] = pd.to_datetime(clean["date"])
    returns = clean.set_index("date")["equity"].pct_change().dropna()
    result = {
        "start": str(clean["date"].iloc[0].date()),
        "end": str(clean["date"].iloc[-1].date()),
        "observations": int(len(clean)),
        "starting_equity": float(clean["equity"].iloc[0]),
        "ending_equity": float(clean["equity"].iloc[-1]),
        "cumulative_return": float(
            clean["equity"].iloc[-1] / clean["equity"].iloc[0] - 1.0
        ),
        "cagr": float(annualized_return(clean)),
        "annualized_volatility": float(annualized_volatility(returns)),
        "sharpe": float(sharpe_ratio(returns)),
        "sortino": float(sortino_ratio(returns)),
        "calmar": float(calmar_ratio(clean)),
        "max_drawdown": float(max_drawdown(clean)),
        "turnover": float(turnover),
        "total_cost": float(total_cost),
        "rebalance_count": int(rebalance_count),
        "exit_count": int(exit_count),
    }
    result["drawdown"] = _drawdown_details(clean)
    return result


def _split_oos(curve: pd.DataFrame) -> tuple[pd.Timestamp, pd.DataFrame]:
    index = max(1, min(len(curve) - 2, int(len(curve) * IN_SAMPLE_FRACTION)))
    split = pd.Timestamp(curve["date"].iloc[index])
    oos = curve.loc[pd.to_datetime(curve["date"]) >= split].reset_index(drop=True)
    return split, oos


def _period_return(curve: pd.DataFrame, start: date, end: date) -> float | None:
    period = _period_curve(curve, start, end)
    if len(period) < 2:
        return None
    return float(period["equity"].iloc[-1] / period["equity"].iloc[0] - 1.0)


def _yearly_returns(curve: pd.DataFrame) -> dict[str, float]:
    dates = pd.to_datetime(curve["date"])
    years: dict[str, float] = {}
    for year in sorted(set(dates.dt.year)):
        group = curve.loc[dates.dt.year == year]
        if len(group) >= 2:
            years[str(year)] = float(
                group["equity"].iloc[-1] / group["equity"].iloc[0] - 1.0
            )
    return years


def _worst_rolling_returns(curve: pd.DataFrame) -> dict[str, dict[str, Any]]:
    series = curve.copy()
    series["date"] = pd.to_datetime(series["date"])
    monthly = series.set_index("date")["equity"].resample("ME").last()
    output: dict[str, dict[str, Any]] = {}
    for months in (1, 3, 6, 12):
        rolling = monthly.pct_change(months).dropna()
        if rolling.empty:
            continue
        end = pd.Timestamp(rolling.idxmin())
        output[str(months)] = {
            "return": float(rolling.loc[end]),
            "end": str(end.date()),
        }
    return output


def _summarize_run(artifact: dict[str, Any]) -> dict[str, Any]:
    curve = artifact["equity_curve"]
    full = _metrics(
        curve,
        turnover=artifact["total_turnover"],
        total_cost=artifact["total_cost"],
        rebalance_count=artifact["rebalance_count"],
        exit_count=artifact["exit_count"],
    )
    split, oos_curve = _split_oos(curve)
    oos = _metrics(
        oos_curve,
        turnover=0.0,
        total_cost=0.0,
        rebalance_count=0,
        exit_count=0,
    )
    folds: dict[str, Any] = {}
    for label, start, end in FOLDS:
        period = _period_curve(curve, start, end)
        folds[label] = _metrics(
            period,
            turnover=0.0,
            total_cost=0.0,
            rebalance_count=0,
            exit_count=0,
        )
    stress = {
        label: _period_return(curve, start, end)
        for label, start, end in STRESS_WINDOWS
    }
    return {
        "full": full,
        "legacy_oos_split": str(split.date()),
        "legacy_oos": oos,
        "folds": folds,
        "stress_returns": stress,
        "yearly_returns": _yearly_returns(curve),
        "worst_rolling_returns": _worst_rolling_returns(curve),
        "regime_calls": artifact["regime_calls"],
        "regime_transition_evidence": artifact["regime_transition_evidence"],
        "final_cash_weight": artifact["final_cash_weight"],
        "final_holding_count": artifact["final_holding_count"],
    }


def _monthly_returns(curve: pd.DataFrame) -> pd.Series:
    clean = curve.copy()
    clean["date"] = pd.to_datetime(clean["date"])
    return clean.set_index("date")["equity"].resample("ME").last().pct_change().dropna()


def _paired_block_bootstrap(
    baseline_curve: pd.DataFrame,
    candidate_curve: pd.DataFrame,
) -> dict[str, float]:
    aligned = pd.concat(
        [_monthly_returns(baseline_curve), _monthly_returns(candidate_curve)],
        axis=1,
        join="inner",
    ).dropna()
    aligned.columns = pd.Index(["baseline", "candidate"])
    if len(aligned) < BLOCK_MONTHS:
        raise ValueError("not enough monthly returns for block bootstrap")
    values = aligned.to_numpy(dtype=float)
    count = len(values)
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    deltas = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    blocks_needed = int(np.ceil(count / BLOCK_MONTHS))
    offsets = np.arange(BLOCK_MONTHS)
    for sample_index in range(BOOTSTRAP_SAMPLES):
        starts = rng.integers(0, count, size=blocks_needed)
        indexes = ((starts[:, None] + offsets[None, :]) % count).ravel()[:count]
        sampled = values[indexes]
        base_log = float(np.log1p(sampled[:, 0]).mean() * 12.0)
        candidate_log = float(np.log1p(sampled[:, 1]).mean() * 12.0)
        deltas[sample_index] = np.expm1(candidate_log) - np.expm1(base_log)
    low, median, high = np.quantile(deltas, [0.025, 0.5, 0.975])
    return {
        "samples": float(BOOTSTRAP_SAMPLES),
        "block_months": float(BLOCK_MONTHS),
        "ci_2_5": float(low),
        "median": float(median),
        "ci_97_5": float(high),
        "probability_delta_positive": float((deltas > 0.0).mean()),
    }


def _log_improvement_share(
    baseline_curve: pd.DataFrame,
    candidate_curve: pd.DataFrame,
    start: date,
    end: date,
) -> dict[str, float | None]:
    base = baseline_curve.copy()
    candidate = candidate_curve.copy()
    base["date"] = pd.to_datetime(base["date"])
    candidate["date"] = pd.to_datetime(candidate["date"])
    aligned = pd.concat(
        [
            base.set_index("date")["equity"].pct_change(),
            candidate.set_index("date")["equity"].pct_change(),
        ],
        axis=1,
        join="inner",
    ).dropna()
    aligned.columns = pd.Index(["baseline", "candidate"])
    delta_log = np.log1p(aligned["candidate"]) - np.log1p(aligned["baseline"])
    total = float(delta_log.sum())
    mask = (delta_log.index >= pd.Timestamp(start)) & (delta_log.index <= pd.Timestamp(end))
    window = float(delta_log.loc[mask].sum())
    share = window / total if total > 0.0 and window > 0.0 else None
    return {
        "total_log_improvement": total,
        "window_log_improvement": window,
        "positive_improvement_share": share,
    }


def _compare(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    baseline_2x: dict[str, Any],
    candidate_2x: dict[str, Any],
) -> dict[str, Any]:
    base_summary = _summarize_run(baseline)
    candidate_summary = _summarize_run(candidate)
    base_full = base_summary["full"]
    candidate_full = candidate_summary["full"]
    fold_deltas = {
        label: (
            candidate_summary["folds"][label]["cagr"]
            - base_summary["folds"][label]["cagr"]
        )
        for label, _start, _end in FOLDS
    }
    positive_folds = sum(delta > 0.0 for delta in fold_deltas.values())
    q4 = _log_improvement_share(
        baseline["equity_curve"],
        candidate["equity_curve"],
        date(2024, 9, 24),
        date(2024, 12, 31),
    )
    base_2x_summary = _summarize_run(baseline_2x)
    candidate_2x_summary = _summarize_run(candidate_2x)
    delta = {
        "cagr": candidate_full["cagr"] - base_full["cagr"],
        "sharpe": candidate_full["sharpe"] - base_full["sharpe"],
        "max_drawdown": (
            candidate_full["max_drawdown"] - base_full["max_drawdown"]
        ),
        "turnover": candidate_full["turnover"] - base_full["turnover"],
        "total_cost": candidate_full["total_cost"] - base_full["total_cost"],
    }
    cost_2x_delta_cagr = (
        candidate_2x_summary["full"]["cagr"] - base_2x_summary["full"]["cagr"]
    )
    q4_share = q4["positive_improvement_share"]
    gates = {
        "delta_cagr": delta["cagr"] >= VERDICT_GATES["min_delta_cagr"],
        "delta_sharpe": delta["sharpe"] >= VERDICT_GATES["min_delta_sharpe"],
        "max_drawdown_floor": (
            candidate_full["max_drawdown"] >= VERDICT_GATES["max_drawdown_floor"]
        ),
        "double_cost_delta_cagr_positive": cost_2x_delta_cagr > 0.0,
        "double_cost_max_drawdown_floor": (
            candidate_2x_summary["full"]["max_drawdown"]
            >= VERDICT_GATES["max_drawdown_floor"]
        ),
        "positive_folds": positive_folds >= VERDICT_GATES["min_positive_folds"],
        "not_2024q4_dominated": (
            q4_share is None
            or q4_share <= VERDICT_GATES["max_2024q4_improvement_share"]
        ),
    }
    all_gates = all(gates.values())
    return {
        "delta": delta,
        "double_cost_delta_cagr": cost_2x_delta_cagr,
        "fold_delta_cagr": fold_deltas,
        "positive_fold_count": positive_folds,
        "q4_contribution": q4,
        "paired_monthly_block_bootstrap": _paired_block_bootstrap(
            baseline["equity_curve"], candidate["equity_curve"]
        ),
        "gates": gates,
        "all_gates_pass": all_gates,
        "historical_verdict": (
            "PAPER_CANDIDATE_C2" if all_gates else "NO_GO"
        ),
    }


def _benchmark_artifact(hs300: pd.DataFrame, dates: pd.Series) -> dict[str, Any]:
    frame = hs300.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    series = frame.drop_duplicates("date", keep="last").set_index("date")["close"].sort_index()
    aligned_dates = pd.DatetimeIndex(pd.to_datetime(dates))
    aligned = series.reindex(aligned_dates, method="ffill")
    if aligned.isna().any():
        raise ValueError("CSI300 benchmark does not cover the strategy window")
    equity = STARTING_CAPITAL * aligned / float(aligned.iloc[0])
    return {
        "equity_curve": pd.DataFrame({"date": aligned_dates, "equity": equity.to_numpy()}),
        "total_turnover": 0.0,
        "total_cost": 0.0,
        "rebalance_count": 0,
        "exit_count": 0,
        "trading_days": int(len(equity)),
        "regime_calls": {"risk_on_calls": 0, "risk_off_calls": 0},
        "regime_transition_evidence": [],
        "final_cash_weight": 0.0,
        "final_holding_count": 1,
    }


def _cache_fingerprint(
    *,
    label: str,
    prices_sha: str,
    universe_sha: str,
    hs300_sha: str,
) -> str:
    raw = "|".join(
        [
            CACHE_VERSION,
            label,
            prices_sha,
            universe_sha,
            hs300_sha,
            _sha256(Path(__file__)),
            _git_head(),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _load_or_run(
    *,
    label: str,
    cache_dir: Path,
    fingerprint: str,
    force: bool,
    runner: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    cache_path = cache_dir / f"{label}.pkl"
    if cache_path.is_file() and not force:
        cached = pd.read_pickle(cache_path)  # noqa: S301 - evaluator-owned cache
        if cached.get("fingerprint") == fingerprint:
            print(f"CACHE {label}", flush=True)
            return dict(cached["artifact"])
    print(f"RUN {label}", flush=True)
    artifact = runner()
    cache_dir.mkdir(parents=True, exist_ok=True)
    pd.to_pickle({"fingerprint": fingerprint, "artifact": artifact}, cache_path)
    print(
        f"DONE {label} ending={artifact['equity_curve']['equity'].iloc[-1]:.2f} "
        f"cost={artifact['total_cost']:.2f}",
        flush=True,
    )
    return artifact


def _regime_metadata(schedule: RegimeSchedule, start: date, end: date) -> dict[str, Any]:
    selected = schedule.states.loc[
        (schedule.states.index >= pd.Timestamp(start) - pd.DateOffset(months=1))
        & (schedule.states.index <= pd.Timestamp(end))
    ]
    transitions = int((selected.astype(int).diff().abs() == 1).sum())
    return {
        "rule": "monthly CSI300 close > trailing 200 trading-day simple moving average",
        "signal_timing": "month-end close; target executes through engine at T+1 open",
        "risk_off_asset": "zero-return CNY cash",
        "states": int(len(selected)),
        "risk_on_states": int(selected.sum()),
        "risk_off_states": int((~selected).sum()),
        "transitions": transitions,
        "first_source_date": str(selected.index.min().date()),
        "last_source_date": str(selected.index.max().date()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    os.environ["WORKBENCH_DATA_ROOT"] = str(B070_ROOT.resolve())
    for path in (PRICES_PATH, UNIVERSE_PATH, HS300_PATH, HS300_CONTROL_PATH):
        if not path.is_file():
            raise FileNotFoundError(path)

    print("HASH inputs", flush=True)
    prices_sha = _sha256(PRICES_PATH)
    universe_sha = _sha256(UNIVERSE_PATH)
    hs300_sha = _sha256(HS300_PATH)
    hs300_control_sha = _sha256(HS300_CONTROL_PATH)
    prices = pd.read_pickle(PRICES_PATH)  # noqa: S301 - trusted project cache
    hs300 = pd.read_csv(HS300_PATH)
    hs300_control = pd.read_csv(HS300_CONTROL_PATH)
    hs300_crosscheck = hs300_control.merge(
        hs300,
        on="date",
        how="inner",
        suffixes=("_control", "_schedule"),
        validate="one_to_one",
    )
    hs300_crosscheck_max_abs_diff = float(
        (hs300_crosscheck["close_control"] - hs300_crosscheck["close_schedule"])
        .abs()
        .max()
    )
    if hs300_crosscheck_max_abs_diff != 0.0:
        raise AssertionError("CSI300 schedule and control closes do not match")
    schedule = _build_regime_schedule(hs300)

    from trade.data.cn_attack_universe import load_cn_universe_history

    universe_history = load_cn_universe_history(universe_path=UNIVERSE_PATH)
    run_specs = {
        "e0_baseline_1x": (False, False, False, 1.0),
        "e1_partial_1x": (True, False, False, 1.0),
        "e2_regime_1x": (False, True, False, 1.0),
        "e0_baseline_2x": (False, False, False, 2.0),
        "e1_partial_2x": (True, False, False, 2.0),
        "e2_regime_2x": (False, True, False, 2.0),
        "e0_baseline_corrected_halt_1x": (False, False, True, 1.0),
        "e1_partial_corrected_halt_1x": (True, False, True, 1.0),
        "e2_regime_corrected_halt_1x": (False, True, True, 1.0),
        "e0_baseline_corrected_halt_2x": (False, False, True, 2.0),
        "e1_partial_corrected_halt_2x": (True, False, True, 2.0),
        "e2_regime_corrected_halt_2x": (False, True, True, 2.0),
    }
    artifacts: dict[str, dict[str, Any]] = {}
    for label, (partial, regime, corrected_halt, cost_multiplier) in run_specs.items():
        fingerprint = _cache_fingerprint(
            label=label,
            prices_sha=prices_sha,
            universe_sha=universe_sha,
            hs300_sha=hs300_sha,
        )
        artifacts[label] = _load_or_run(
            label=label,
            cache_dir=args.cache_dir,
            fingerprint=fingerprint,
            force=args.force,
            runner=lambda partial=partial, regime=regime, corrected_halt=corrected_halt,
            cost_multiplier=cost_multiplier: (
                _run_variant(
                    prices=prices,
                    universe_history=universe_history,
                    schedule=schedule,
                    partial_rebalance=partial,
                    use_regime_gate=regime,
                    corrected_halt_mask=corrected_halt,
                    cost_multiplier=cost_multiplier,
                )
            ),
        )

    benchmark = _benchmark_artifact(
        hs300_control, artifacts["e0_baseline_1x"]["equity_curve"]["date"]
    )
    summaries = {label: _summarize_run(artifact) for label, artifact in artifacts.items()}
    comparisons = {
        "e1_partial_vs_e0_shipped_halt_mask": _compare(
            artifacts["e0_baseline_1x"],
            artifacts["e1_partial_1x"],
            artifacts["e0_baseline_2x"],
            artifacts["e1_partial_2x"],
        ),
        "e2_regime_vs_e0_shipped_halt_mask": _compare(
            artifacts["e0_baseline_1x"],
            artifacts["e2_regime_1x"],
            artifacts["e0_baseline_2x"],
            artifacts["e2_regime_2x"],
        ),
        "e1_partial_vs_e0_corrected_halt_mask": _compare(
            artifacts["e0_baseline_corrected_halt_1x"],
            artifacts["e1_partial_corrected_halt_1x"],
            artifacts["e0_baseline_corrected_halt_2x"],
            artifacts["e1_partial_corrected_halt_2x"],
        ),
        "e2_regime_vs_e0_corrected_halt_mask": _compare(
            artifacts["e0_baseline_corrected_halt_1x"],
            artifacts["e2_regime_corrected_halt_1x"],
            artifacts["e0_baseline_corrected_halt_2x"],
            artifacts["e2_regime_corrected_halt_2x"],
        ),
    }
    baseline_matches_b081 = {
        "full_cagr": abs(summaries["e0_baseline_1x"]["full"]["cagr"] - 0.1168) < 0.00015,
        "full_sharpe": abs(summaries["e0_baseline_1x"]["full"]["sharpe"] - 0.532) < 0.0006,
        "legacy_oos_cagr": abs(
            summaries["e0_baseline_1x"]["legacy_oos"]["cagr"] - 0.2713
        )
        < 0.00015,
        "legacy_oos_sharpe": abs(
            summaries["e0_baseline_1x"]["legacy_oos"]["sharpe"] - 0.959
        )
        < 0.0006,
    }
    if not all(baseline_matches_b081.values()):
        raise AssertionError(f"E0 does not reproduce B081: {baseline_matches_b081}")
    if artifacts["e2_regime_1x"]["regime_calls"]["risk_off_calls"] <= 0:
        raise AssertionError("E2 regime gate never entered risk-off")
    if (
        artifacts["e2_regime_corrected_halt_1x"]["regime_calls"]["risk_off_calls"]
        <= 0
    ):
        raise AssertionError("corrected-halt E2 regime gate never entered risk-off")

    def semantic_consensus(shipped_label: str, corrected_label: str) -> str:
        shipped_pass = bool(comparisons[shipped_label]["all_gates_pass"])
        corrected_pass = bool(comparisons[corrected_label]["all_gates_pass"])
        if shipped_pass and corrected_pass:
            return "PAPER_CANDIDATE_C2"
        if not shipped_pass and not corrected_pass:
            return "NO_GO"
        return "INCONCLUSIVE_HALT_SEMANTICS"

    halted = prices.loc[
        (pd.to_datetime(prices["date"]) >= pd.Timestamp(START))
        & prices["tradestatus"].eq(0)
    ]
    semantics = {
        "halt_rows": int(len(halted)),
        "halt_rows_with_non_null_adj_close": int(halted["adj_close"].notna().sum()),
        "halt_rows_with_zero_volume": int(halted["volume"].eq(0).sum()),
        "shipped_mask_issue": (
            "_real_bar_mask uses adj_close.notna, so carried-price halt rows are "
            "usually classified as tradeable"
        ),
        "sensitivity_fix": "tradestatus == 1",
        "unresolved_price_limit_issue": (
            "engine freezes both directions although up-limit should only block buys "
            "and down-limit should only block sells"
        ),
        "unresolved_lot_price_issue": (
            "qfq prices are used for 100-share affordability and are not raw historical "
            "transaction prices"
        ),
    }

    output = {
        "metadata": {
            "research_date": "2026-07-11",
            "git_head": _git_head(),
            "research_boundary": "research-only/advisory-only/no broker/no real money",
            "contamination": "C2-DIRECT: 2019-2026 history was inspected in prior batches",
            "positive_result_limit": "at most paper candidate; not deployable GO",
            "window": {"start": str(START), "end": summaries["e0_baseline_1x"]["full"]["end"]},
            "capital_cny": STARTING_CAPITAL,
            "input_checksums": {
                "prices_pickle_sha256": prices_sha,
                "pit_universe_sha256": universe_sha,
                "hs300_sha256": hs300_sha,
                "hs300_control_sha256": hs300_control_sha,
            },
            "hs300_crosscheck": {
                "overlap_rows": int(len(hs300_crosscheck)),
                "max_abs_close_difference": hs300_crosscheck_max_abs_diff,
            },
        },
        "protocol": {
            "e0": "pure_momentum/equal/Top25/full fidelity/20% aggregate band",
            "e1": "E0 plus existing partial_rebalance=True and fixed 0.5% per-name threshold",
            "e2": "E0 plus frozen monthly CSI300 close > MA200 exposure gate; risk-off cash",
            "halt_semantics": (
                "run both shipped adj_close-not-null mask and evaluator sensitivity "
                "tradestatus==1 mask"
            ),
            "primary_cost_bps": PRIMARY_COST_BPS,
            "double_cost_multiplier": 2.0,
            "verdict_gates": VERDICT_GATES,
            "folds": [
                {"label": label, "start": str(start), "end": str(end)}
                for label, start, end in FOLDS
            ],
        },
        "regime": _regime_metadata(schedule, START, date(2026, 6, 18)),
        "engine_data_semantics": semantics,
        "baseline_reproduction": baseline_matches_b081,
        "runs": summaries,
        "benchmark_hs300_price_only": _summarize_run(benchmark),
        "comparisons": comparisons,
        "semantic_consensus": {
            "e1_partial": semantic_consensus(
                "e1_partial_vs_e0_shipped_halt_mask",
                "e1_partial_vs_e0_corrected_halt_mask",
            ),
            "e2_regime": semantic_consensus(
                "e2_regime_vs_e0_shipped_halt_mask",
                "e2_regime_vs_e0_corrected_halt_mask",
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"WROTE {args.output}", flush=True)
    for label, comparison in comparisons.items():
        print(
            f"VERDICT {label}={comparison['historical_verdict']} "
            f"delta_cagr={comparison['delta']['cagr']:.4f} "
            f"delta_sharpe={comparison['delta']['sharpe']:.4f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
