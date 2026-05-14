"""B018 F002 — unit tests for trade.analysis.parameter_sweep.

Tests use a deterministic synthetic 9-asset universe (mirrors the B013
universe shape) so the sweep harness can drive the real B010 / B013
backtest entry points without depending on the B014 yfinance manifest.

Coverage:
- Each sweep returns the spec-mandated number of rows.
- Results are deterministic across two consecutive runs.
- Default ``RiskParityParameters`` / ``RegimeAdaptiveConfig`` are not
  mutated by sweep iterations.
- Unsupported cadence values are skipped with a diagnostic reason.
- Skipped variants (universe missing required defensive / regime asset)
  produce a row with ``status='skipped'`` and a non-empty reason.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from trade.analysis.parameter_sweep import (
    CADENCE_ANNUAL,
    CADENCE_MONTHLY,
    CADENCE_QUARTERLY,
    CADENCE_SEMIANNUAL,
    DEFAULT_CADENCES,
    DEFAULT_UNIVERSE_VARIANTS,
    DEFAULT_VOL_TARGETS,
    DIMENSION_CADENCE,
    DIMENSION_UNIVERSE,
    DIMENSION_VOL_TARGET,
    STATUS_RAN,
    STATUS_SKIPPED,
    STRATEGY_B010,
    STRATEGY_B013,
    SUPPORTED_CADENCES,
    SweepWindow,
    UniverseVariant,
    build_monthly_signal_dates,
    run_cadence_sweep,
    run_universe_ablation_sweep,
    run_vol_target_sweep,
)
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import RegimeAdaptiveConfig
from trade.strategies.risk_parity import RiskParityParameters

# --------------------------------------------------------------------------- #
# Synthetic 9-asset fixture (~2-year history to cover the default lookbacks)
# --------------------------------------------------------------------------- #


_B013_UNIVERSE: tuple[str, ...] = (
    "SPY",
    "QQQ",
    "VEA",
    "VWO",
    "IEF",
    "TLT",
    "GLD",
    "DBC",
    "SGOV",
)


def _amplitude_for(symbol: str) -> float:
    return {
        "SPY": 0.018,
        "QQQ": 0.022,
        "VEA": 0.020,
        "VWO": 0.025,
        "IEF": 0.006,
        "TLT": 0.012,
        "GLD": 0.012,
        "DBC": 0.020,
        "SGOV": 0.0005,
    }[symbol]


def _phase_for(symbol: str) -> int:
    return {
        "SPY": 0,
        "QQQ": 0,
        "VEA": 0,
        "VWO": 0,
        "IEF": 1,
        "TLT": 1,
        "GLD": 0,
        "DBC": 1,
        "SGOV": 0,
    }[symbol]


def _synthetic_records(days: int = 800) -> tuple[PriceBar, ...]:
    start = date(2022, 1, 3)
    bars: list[PriceBar] = []
    for index, symbol in enumerate(_B013_UNIVERSE):
        price = 100.0 + index
        amp = _amplitude_for(symbol)
        phase = _phase_for(symbol)
        current = start
        observation = 0
        while observation < days:
            if current.weekday() < 5:
                if observation:
                    step = amp if (observation + phase) % 2 == 0 else -amp * 0.95
                    price *= 1.0 + step
                bars.append(
                    PriceBar(
                        date=current,
                        symbol=symbol,
                        open=price * 0.999,
                        close=price,
                        adjusted_close=price,
                        volume=1000,
                    )
                )
                observation += 1
            current += timedelta(days=1)
    return tuple(bars)


def _window() -> SweepWindow:
    return SweepWindow(
        name="test_window",
        start_date=date(2023, 9, 1),
        end_date=date(2024, 4, 30),
        benchmark_ending_value=110_000.0,
    )


def _short_window() -> SweepWindow:
    return SweepWindow(
        name="short",
        start_date=date(2023, 12, 1),
        end_date=date(2024, 2, 28),
        benchmark_ending_value=None,
    )


# --------------------------------------------------------------------------- #
# Vol-target sweep
# --------------------------------------------------------------------------- #


def test_vol_target_sweep_returns_expected_count_per_strategy() -> None:
    records = _synthetic_records()
    targets = DEFAULT_VOL_TARGETS
    windows = (_window(),)

    results = run_vol_target_sweep(records, STRATEGY_B010, targets, windows)

    assert len(results) == len(targets) * len(windows)
    assert {row.dimension for row in results} == {DIMENSION_VOL_TARGET}
    assert {row.strategy for row in results} == {STRATEGY_B010}
    assert {row.window for row in results} == {windows[0].name}


def test_vol_target_sweep_produces_deterministic_results() -> None:
    records = _synthetic_records()
    targets = (0.08, 0.10)
    windows = (_window(),)

    first = run_vol_target_sweep(records, STRATEGY_B010, targets, windows)
    second = run_vol_target_sweep(records, STRATEGY_B010, targets, windows)

    assert first == second


def test_vol_target_sweep_does_not_mutate_strategy_defaults() -> None:
    records = _synthetic_records()
    targets = (0.10, 0.12)
    windows = (_window(),)

    pre_b010_default = RiskParityParameters()
    pre_b013_default = RegimeAdaptiveConfig()
    pre_b010_target = pre_b010_default.target_volatility
    pre_b013_target = pre_b013_default.target_volatility

    run_vol_target_sweep(records, STRATEGY_B010, targets, windows)
    run_vol_target_sweep(records, STRATEGY_B013, targets, windows)

    post_b010_default = RiskParityParameters()
    post_b013_default = RegimeAdaptiveConfig()
    assert post_b010_default.target_volatility == pre_b010_target
    assert post_b013_default.target_volatility == pre_b013_target
    # Frozen dataclasses cannot be mutated, but verify the instance fields
    # we held a handle to also remain unchanged.
    assert pre_b010_default.target_volatility == pre_b010_target
    assert pre_b013_default.target_volatility == pre_b013_target


def test_vol_target_sweep_records_gap_when_benchmark_provided() -> None:
    records = _synthetic_records()
    windows = (
        SweepWindow(
            name="bench_window",
            start_date=date(2023, 9, 1),
            end_date=date(2024, 4, 30),
            benchmark_ending_value=110_000.0,
        ),
    )

    results = run_vol_target_sweep(records, STRATEGY_B010, (0.08,), windows)

    assert len(results) == 1
    row = results[0]
    assert row.status == STATUS_RAN
    assert row.gap_vs_60_40 == pytest.approx(row.ending_value - 110_000.0)


def test_vol_target_sweep_skips_non_positive_target() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    results = run_vol_target_sweep(records, STRATEGY_B010, (0.0, 0.08), windows)

    assert len(results) == 2
    skipped = [row for row in results if row.value == "0.0"]
    ran = [row for row in results if row.value == "0.08"]
    assert len(skipped) == 1
    assert len(ran) == 1
    assert skipped[0].status == STATUS_SKIPPED
    assert skipped[0].skipped_reason is not None
    assert "positive" in skipped[0].skipped_reason
    assert ran[0].status == STATUS_RAN


# --------------------------------------------------------------------------- #
# Universe ablation sweep
# --------------------------------------------------------------------------- #


def test_universe_ablation_sweep_runs_supported_variants() -> None:
    records = _synthetic_records()
    # Use B013-friendly variants: full + drop_stabilizers (both contain
    # SPY + SGOV which the B013 invariants require).
    variants = (
        UniverseVariant("full", _B013_UNIVERSE),
        UniverseVariant("drop_stabilizers", ("SPY", "QQQ", "VEA", "VWO", "SGOV")),
    )
    windows = (_window(),)

    results = run_universe_ablation_sweep(records, STRATEGY_B013, variants, windows)

    assert len(results) == 2
    assert {row.value for row in results} == {"full", "drop_stabilizers"}
    for row in results:
        assert row.status == STATUS_RAN
        assert row.dimension == DIMENSION_UNIVERSE


def test_universe_ablation_skips_variant_missing_defensive() -> None:
    records = _synthetic_records()
    variants = (
        UniverseVariant("spy_ief", ("SPY", "IEF")),  # missing SGOV
    )
    windows = (_window(),)

    results = run_universe_ablation_sweep(records, STRATEGY_B010, variants, windows)

    assert len(results) == 1
    row = results[0]
    assert row.status == STATUS_SKIPPED
    assert row.skipped_reason is not None
    assert "SGOV" in row.skipped_reason
    assert row.ending_value == 0.0


def test_universe_ablation_skips_variant_missing_b013_spy() -> None:
    records = _synthetic_records()
    variants = (
        UniverseVariant("no_spy", ("QQQ", "VEA", "VWO", "SGOV")),
    )
    windows = (_window(),)

    results = run_universe_ablation_sweep(records, STRATEGY_B013, variants, windows)

    assert len(results) == 1
    row = results[0]
    assert row.status == STATUS_SKIPPED
    assert row.skipped_reason is not None
    assert "SPY" in row.skipped_reason


def test_universe_ablation_does_not_mutate_strategy_defaults() -> None:
    records = _synthetic_records()
    variants = (
        UniverseVariant("full", _B013_UNIVERSE),
        UniverseVariant("drop_stabilizers", ("SPY", "QQQ", "VEA", "VWO", "SGOV")),
    )
    windows = (_window(),)

    pre_b013_universe = tuple(entry.symbol for entry in RegimeAdaptiveConfig().universe)
    pre_b010_universe = RiskParityParameters().universe

    run_universe_ablation_sweep(records, STRATEGY_B013, variants, windows)
    run_universe_ablation_sweep(
        records,
        STRATEGY_B010,
        (UniverseVariant("full", _B013_UNIVERSE),),
        windows,
    )

    post_b013_universe = tuple(entry.symbol for entry in RegimeAdaptiveConfig().universe)
    post_b010_universe = RiskParityParameters().universe
    assert post_b013_universe == pre_b013_universe
    assert post_b010_universe == pre_b010_universe


def test_universe_ablation_default_variants_constant_has_required_set() -> None:
    """The spec-mandated default variants tuple must include at least the
    four named in B018 acceptance (full / drop_sgov / drop_stabilizers /
    spy_ief or spy_only)."""

    names = {variant.name for variant in DEFAULT_UNIVERSE_VARIANTS}
    assert "full" in names
    assert "drop_sgov" in names
    assert "drop_stabilizers" in names
    assert {"spy_ief", "spy_only"} & names  # at least one minimal-equity variant


# --------------------------------------------------------------------------- #
# Cadence sweep
# --------------------------------------------------------------------------- #


def test_cadence_sweep_runs_all_supported_cadences() -> None:
    records = _synthetic_records()
    windows = (_window(),)
    cadences = DEFAULT_CADENCES

    results = run_cadence_sweep(records, STRATEGY_B010, cadences, windows)

    assert len(results) == len(cadences)
    assert {row.value for row in results} == set(cadences)
    for row in results:
        assert row.status == STATUS_RAN
        assert row.dimension == DIMENSION_CADENCE


def test_cadence_sweep_quarterly_runs_fewer_rebalances_than_monthly() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    monthly_results = run_cadence_sweep(records, STRATEGY_B010, (CADENCE_MONTHLY,), windows)
    quarterly_results = run_cadence_sweep(records, STRATEGY_B010, (CADENCE_QUARTERLY,), windows)

    assert monthly_results[0].status == STATUS_RAN
    assert quarterly_results[0].status == STATUS_RAN
    assert quarterly_results[0].rebalance_count < monthly_results[0].rebalance_count


def test_cadence_sweep_skips_unknown_cadence_with_diagnostic() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    results = run_cadence_sweep(
        records,
        STRATEGY_B010,
        (CADENCE_MONTHLY, "weekly", "biweekly", CADENCE_ANNUAL),
        windows,
    )

    by_value = {row.value: row for row in results}
    assert by_value[CADENCE_MONTHLY].status == STATUS_RAN
    assert by_value[CADENCE_ANNUAL].status == STATUS_RAN
    assert by_value["weekly"].status == STATUS_SKIPPED
    assert by_value["weekly"].skipped_reason is not None
    assert "supported" in by_value["weekly"].skipped_reason
    assert by_value["biweekly"].status == STATUS_SKIPPED


def test_cadence_sweep_handles_too_short_window_for_annual_stride() -> None:
    records = _synthetic_records()
    windows = (_short_window(),)  # only a few months — annual stride may yield one date

    results = run_cadence_sweep(records, STRATEGY_B010, (CADENCE_ANNUAL,), windows)

    assert len(results) == 1
    row = results[0]
    # Either ran (one rebalance) or skipped if no dates landed in window — both acceptable.
    assert row.status in {STATUS_RAN, STATUS_SKIPPED}


def test_cadence_sweep_does_not_mutate_strategy_defaults() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    pre_b010 = RiskParityParameters()
    pre_b013 = RegimeAdaptiveConfig()

    run_cadence_sweep(records, STRATEGY_B010, DEFAULT_CADENCES, windows)
    run_cadence_sweep(records, STRATEGY_B013, DEFAULT_CADENCES, windows)

    post_b010 = RiskParityParameters()
    post_b013 = RegimeAdaptiveConfig()
    assert post_b010 == pre_b010
    assert pre_b013.target_volatility == post_b013.target_volatility
    assert tuple(e.symbol for e in pre_b013.universe) == tuple(
        e.symbol for e in post_b013.universe
    )


# --------------------------------------------------------------------------- #
# Strategy validation
# --------------------------------------------------------------------------- #


def test_unknown_strategy_rejected_by_vol_target_sweep() -> None:
    records = _synthetic_records()
    with pytest.raises(ValueError, match="unknown strategy"):
        run_vol_target_sweep(records, "b099", (0.08,), (_window(),))


def test_unknown_strategy_rejected_by_universe_sweep() -> None:
    records = _synthetic_records()
    with pytest.raises(ValueError, match="unknown strategy"):
        run_universe_ablation_sweep(
            records,
            "b099",
            (UniverseVariant("full", _B013_UNIVERSE),),
            (_window(),),
        )


def test_unknown_strategy_rejected_by_cadence_sweep() -> None:
    records = _synthetic_records()
    with pytest.raises(ValueError, match="unknown strategy"):
        run_cadence_sweep(records, "b099", (CADENCE_MONTHLY,), (_window(),))


# --------------------------------------------------------------------------- #
# Public constants sanity
# --------------------------------------------------------------------------- #


def test_default_vol_targets_match_spec() -> None:
    assert DEFAULT_VOL_TARGETS == (0.05, 0.08, 0.10, 0.12, 0.15)


def test_supported_cadences_match_spec() -> None:
    assert frozenset(
        {CADENCE_MONTHLY, CADENCE_QUARTERLY, CADENCE_SEMIANNUAL, CADENCE_ANNUAL}
    ) == SUPPORTED_CADENCES


def test_default_cadences_in_canonical_order() -> None:
    assert DEFAULT_CADENCES == (
        CADENCE_MONTHLY,
        CADENCE_QUARTERLY,
        CADENCE_SEMIANNUAL,
        CADENCE_ANNUAL,
    )


def test_default_universe_variants_have_at_least_four_entries() -> None:
    assert len(DEFAULT_UNIVERSE_VARIANTS) >= 4


# --------------------------------------------------------------------------- #
# build_monthly_signal_dates helper
# --------------------------------------------------------------------------- #


def test_build_monthly_signal_dates_picks_last_trading_day_of_month() -> None:
    trading_dates = (
        date(2024, 1, 30),
        date(2024, 1, 31),
        date(2024, 2, 1),
        date(2024, 2, 29),
        date(2024, 3, 28),
        date(2024, 3, 29),
    )

    signal_dates = build_monthly_signal_dates(
        trading_dates, date(2024, 1, 1), date(2024, 3, 31)
    )

    assert signal_dates == (date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 29))


def test_build_monthly_signal_dates_empty_when_window_reversed() -> None:
    trading_dates = (date(2024, 1, 31), date(2024, 2, 29))

    assert build_monthly_signal_dates(trading_dates, date(2024, 3, 1), date(2024, 1, 1)) == ()
