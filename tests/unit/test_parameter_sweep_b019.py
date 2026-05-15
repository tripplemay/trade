"""B019 F001 — unit tests for trade.analysis.parameter_sweep extension.

Covers ``run_cadence_vs_default_sweep`` (joint cadence × vol_target sweep
plus default baseline) and ``evaluate_retune_gate`` (the four-condition
retune verdict) added in B019.

The sweep tests reuse the synthetic 9-asset fixture established in
``tests/unit/test_parameter_sweep.py``; the gate tests build hand-rolled
``SweepRunResult`` lists so the four pass / fail scenarios are
deterministic and do not depend on real backtest outputs.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date, timedelta

import pytest

from trade.analysis.parameter_sweep import (
    CADENCE_MONTHLY,
    CADENCE_QUARTERLY,
    DEFAULT_GATE,
    DIMENSION_CADENCE_VOL_TARGET,
    STATUS_RAN,
    STATUS_SKIPPED,
    STRATEGY_B010,
    STRATEGY_B013,
    CellGateVerdict,
    RetuneGate,
    RetuneGateVerdict,
    SweepRunResult,
    SweepWindow,
    evaluate_retune_gate,
    run_cadence_vs_default_sweep,
)
from trade.data.loader import PriceBar
from trade.strategies.regime_adaptive.config import RegimeAdaptiveConfig
from trade.strategies.risk_parity import RiskParityParameters

# --------------------------------------------------------------------------- #
# Synthetic 9-asset fixture (mirror of test_parameter_sweep.py)
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


# --------------------------------------------------------------------------- #
# run_cadence_vs_default_sweep — cell shape + baseline + non-mutation
# --------------------------------------------------------------------------- #


def test_run_cadence_vs_default_sweep_returns_grid_plus_baseline_count() -> None:
    records = _synthetic_records()
    cadences = (CADENCE_MONTHLY, CADENCE_QUARTERLY)
    vol_targets = (0.09, 0.10, 0.11)
    windows = (_window(),)

    results = run_cadence_vs_default_sweep(
        records, STRATEGY_B010, cadences, vol_targets, windows
    )

    expected = len(cadences) * len(vol_targets) + 1
    assert len(results) == expected
    sweep_rows = [row for row in results if not row.is_baseline]
    baseline_rows = [row for row in results if row.is_baseline]
    assert len(sweep_rows) == len(cadences) * len(vol_targets)
    assert len(baseline_rows) == 1
    for row in results:
        assert row.dimension == DIMENSION_CADENCE_VOL_TARGET
        assert row.cadence is not None
        assert row.vol_target is not None


def test_run_cadence_vs_default_sweep_baseline_disabled_drops_baseline() -> None:
    records = _synthetic_records()
    cadences = (CADENCE_MONTHLY,)
    vol_targets = (0.10,)
    windows = (_window(),)

    results = run_cadence_vs_default_sweep(
        records,
        STRATEGY_B010,
        cadences,
        vol_targets,
        windows,
        default_baseline=False,
    )

    assert len(results) == 1
    assert results[0].is_baseline is False


def test_run_cadence_vs_default_sweep_baseline_uses_actual_b010_default() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    results = run_cadence_vs_default_sweep(
        records,
        STRATEGY_B010,
        (CADENCE_MONTHLY, CADENCE_QUARTERLY),
        (0.09, 0.11),
        windows,
    )

    baseline_rows = [row for row in results if row.is_baseline]
    assert len(baseline_rows) == 1
    baseline = baseline_rows[0]
    default_b010 = RiskParityParameters()
    assert baseline.cadence == default_b010.rebalance_frequency
    assert baseline.vol_target == pytest.approx(default_b010.target_volatility)
    # Sanity: this is not just a hardcoded "monthly" / 0.08 — the assertion
    # is wired to the live default. If F003 mutates the default later, this
    # test still passes because it reads RiskParityParameters() afresh.


def test_run_cadence_vs_default_sweep_baseline_uses_actual_b013_default() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    results = run_cadence_vs_default_sweep(
        records,
        STRATEGY_B013,
        (CADENCE_MONTHLY, CADENCE_QUARTERLY),
        (0.09, 0.11),
        windows,
    )

    baseline_rows = [row for row in results if row.is_baseline]
    assert len(baseline_rows) == 1
    baseline = baseline_rows[0]
    default_b013 = RegimeAdaptiveConfig()
    # B013's config has no rebalance_frequency field today; the harness
    # default cadence is monthly. F003 may add such a field; if it does
    # the helper should be updated to read it and this assertion will be
    # the canary.
    assert baseline.cadence == CADENCE_MONTHLY
    assert baseline.vol_target == pytest.approx(default_b013.target_volatility)


def test_run_cadence_vs_default_sweep_does_not_mutate_strategy_defaults() -> None:
    records = _synthetic_records()
    cadences = (CADENCE_MONTHLY, CADENCE_QUARTERLY)
    vol_targets = (0.09, 0.11)
    windows = (_window(),)

    pre_b010 = RiskParityParameters()
    pre_b013 = RegimeAdaptiveConfig()
    pre_b010_target = pre_b010.target_volatility
    pre_b010_cadence = pre_b010.rebalance_frequency
    pre_b013_target = pre_b013.target_volatility

    run_cadence_vs_default_sweep(
        records, STRATEGY_B010, cadences, vol_targets, windows
    )
    run_cadence_vs_default_sweep(
        records, STRATEGY_B013, cadences, vol_targets, windows
    )

    post_b010 = RiskParityParameters()
    post_b013 = RegimeAdaptiveConfig()
    assert post_b010.target_volatility == pre_b010_target
    assert post_b010.rebalance_frequency == pre_b010_cadence
    assert post_b013.target_volatility == pre_b013_target
    # The original instance handles must also be unchanged (frozen
    # dataclasses guarantee this, but verify defensively).
    assert pre_b010.target_volatility == pre_b010_target
    assert pre_b013.target_volatility == pre_b013_target


def test_run_cadence_vs_default_sweep_is_deterministic() -> None:
    records = _synthetic_records()
    cadences = (CADENCE_MONTHLY, CADENCE_QUARTERLY)
    vol_targets = (0.09, 0.10)
    windows = (_window(),)

    first = run_cadence_vs_default_sweep(
        records, STRATEGY_B010, cadences, vol_targets, windows
    )
    second = run_cadence_vs_default_sweep(
        records, STRATEGY_B010, cadences, vol_targets, windows
    )

    assert first == second


def test_run_cadence_vs_default_sweep_skips_unsupported_cadence() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    results = run_cadence_vs_default_sweep(
        records,
        STRATEGY_B010,
        (CADENCE_MONTHLY, "weekly"),
        (0.10,),
        windows,
    )

    by_value = {(row.cadence, row.is_baseline): row for row in results}
    weekly_row = by_value[("weekly", False)]
    assert weekly_row.status == STATUS_SKIPPED
    assert weekly_row.skipped_reason is not None
    assert "supported" in weekly_row.skipped_reason


def test_run_cadence_vs_default_sweep_skips_non_positive_vol_target() -> None:
    records = _synthetic_records()
    windows = (_window(),)

    results = run_cadence_vs_default_sweep(
        records,
        STRATEGY_B010,
        (CADENCE_MONTHLY,),
        (0.0, 0.10),
        windows,
    )

    sweep_rows = [row for row in results if not row.is_baseline]
    by_target = {row.vol_target: row for row in sweep_rows}
    assert by_target[0.0].status == STATUS_SKIPPED
    assert by_target[0.0].skipped_reason is not None
    assert "positive" in by_target[0.0].skipped_reason
    assert by_target[0.10].status == STATUS_RAN


def test_run_cadence_vs_default_sweep_rejects_unknown_strategy() -> None:
    records = _synthetic_records()
    with pytest.raises(ValueError, match="unknown strategy"):
        run_cadence_vs_default_sweep(
            records, "b099", (CADENCE_MONTHLY,), (0.10,), (_window(),)
        )


# --------------------------------------------------------------------------- #
# evaluate_retune_gate — synthetic SweepRunResult fixtures for 4 scenarios
# --------------------------------------------------------------------------- #


_CALM = "calm"
_STRESS_1 = "stress1"
_STRESS_2 = "stress2"
_STRATEGY = STRATEGY_B010
_DEFAULT_CADENCE = CADENCE_MONTHLY
_DEFAULT_VT = 0.08


def _baseline_row(
    *, window: str, ending_value: float, gap_vs_60_40: float,
    max_drawdown: float, turnover: float,
) -> SweepRunResult:
    return SweepRunResult(
        strategy=_STRATEGY,
        dimension=DIMENSION_CADENCE_VOL_TARGET,
        value="default",
        window=window,
        status=STATUS_RAN,
        skipped_reason=None,
        ending_value=ending_value,
        gap_vs_60_40=gap_vs_60_40,
        max_drawdown=max_drawdown,
        turnover=turnover,
        transaction_costs=100.0,
        sharpe=0.3,
        rebalance_count=10,
        cadence=_DEFAULT_CADENCE,
        vol_target=_DEFAULT_VT,
        is_baseline=True,
    )


def _cell_row(
    *, cadence: str, vol_target: float, window: str,
    ending_value: float, gap_vs_60_40: float,
    max_drawdown: float, turnover: float,
) -> SweepRunResult:
    return SweepRunResult(
        strategy=_STRATEGY,
        dimension=DIMENSION_CADENCE_VOL_TARGET,
        value=f"{cadence}@{vol_target:.4f}",
        window=window,
        status=STATUS_RAN,
        skipped_reason=None,
        ending_value=ending_value,
        gap_vs_60_40=gap_vs_60_40,
        max_drawdown=max_drawdown,
        turnover=turnover,
        transaction_costs=110.0,
        sharpe=0.4,
        rebalance_count=10,
        cadence=cadence,
        vol_target=vol_target,
        is_baseline=False,
    )


def _three_window_baselines() -> list[SweepRunResult]:
    # Default starting capital is 100k; benchmark on calm window = 110k so a
    # baseline ending at 100k corresponds to a -10pp gap (gap_vs_60_40 = -10k).
    return [
        _baseline_row(
            window=_CALM,
            ending_value=100_000.0,
            gap_vs_60_40=-10_000.0,
            max_drawdown=-0.20,
            turnover=2.00,
        ),
        _baseline_row(
            window=_STRESS_1,
            ending_value=95_000.0,
            gap_vs_60_40=0.0,
            max_drawdown=-0.15,
            turnover=1.00,
        ),
        _baseline_row(
            window=_STRESS_2,
            ending_value=99_000.0,
            gap_vs_60_40=0.0,
            max_drawdown=-0.10,
            turnover=1.00,
        ),
    ]


def test_evaluate_retune_gate_all_pass_winning_cell() -> None:
    cadence = CADENCE_QUARTERLY
    vt = 0.10
    rows = _three_window_baselines() + [
        # calm: +6% uplift, gap narrows by 6pp, turnover +2.5%.
        _cell_row(
            cadence=cadence, vol_target=vt, window=_CALM,
            ending_value=106_000.0, gap_vs_60_40=-4_000.0,
            max_drawdown=-0.20, turnover=2.05,
        ),
        # stress1: DD improves -0.15 -> -0.10 (delta +0.05).
        _cell_row(
            cadence=cadence, vol_target=vt, window=_STRESS_1,
            ending_value=96_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.10, turnover=1.00,
        ),
        # stress2: DD improves -0.10 -> -0.05 (delta +0.05).
        _cell_row(
            cadence=cadence, vol_target=vt, window=_STRESS_2,
            ending_value=100_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.05, turnover=1.00,
        ),
    ]

    verdict = evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )

    assert verdict.gate_met is True
    assert verdict.winning_cell == (cadence, vt)
    assert verdict.default_cadence == _DEFAULT_CADENCE
    assert verdict.default_vol_target == pytest.approx(_DEFAULT_VT)
    assert len(verdict.cells) == 1
    cell = verdict.cells[0]
    assert cell.all_pass is True
    assert cell.calm_uplift_pct == pytest.approx(6.0)
    assert cell.calm_gap_narrowing_pp == pytest.approx(6.0)
    assert cell.turnover_increase_pct == pytest.approx(2.5)
    assert cell.pass_stress_do_no_harm is True


def test_evaluate_retune_gate_fails_gate_3_when_stress_dd_worsens() -> None:
    cadence = CADENCE_QUARTERLY
    vt = 0.12
    rows = _three_window_baselines() + [
        # calm: +6% uplift, gap narrows 6pp, turnover only +2.5% — passes 1, 2, 4.
        _cell_row(
            cadence=cadence, vol_target=vt, window=_CALM,
            ending_value=106_000.0, gap_vs_60_40=-4_000.0,
            max_drawdown=-0.20, turnover=2.05,
        ),
        # stress1: DD worsens from -0.15 to -0.18 — fails do-no-harm.
        _cell_row(
            cadence=cadence, vol_target=vt, window=_STRESS_1,
            ending_value=92_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.18, turnover=1.00,
        ),
        # stress2: still improves.
        _cell_row(
            cadence=cadence, vol_target=vt, window=_STRESS_2,
            ending_value=100_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.05, turnover=1.00,
        ),
    ]

    verdict = evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )

    assert verdict.gate_met is False
    assert verdict.winning_cell is None
    cell = verdict.cells[0]
    assert cell.pass_calm_uplift is True
    assert cell.pass_calm_gap_narrowing is True
    assert cell.pass_turnover is True
    assert cell.pass_stress_do_no_harm is False
    assert cell.all_pass is False


def test_evaluate_retune_gate_fails_gate_4_when_turnover_balloons() -> None:
    cadence = CADENCE_MONTHLY
    vt = 0.13
    rows = _three_window_baselines() + [
        # calm: passes uplift + gap; turnover up by 25% -> fails gate 4.
        _cell_row(
            cadence=cadence, vol_target=vt, window=_CALM,
            ending_value=106_000.0, gap_vs_60_40=-4_000.0,
            max_drawdown=-0.20, turnover=2.50,
        ),
        _cell_row(
            cadence=cadence, vol_target=vt, window=_STRESS_1,
            ending_value=96_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.10, turnover=1.20,
        ),
        _cell_row(
            cadence=cadence, vol_target=vt, window=_STRESS_2,
            ending_value=100_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.05, turnover=1.20,
        ),
    ]

    verdict = evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )

    assert verdict.gate_met is False
    assert verdict.winning_cell is None
    cell = verdict.cells[0]
    assert cell.pass_calm_uplift is True
    assert cell.pass_calm_gap_narrowing is True
    assert cell.pass_stress_do_no_harm is True
    assert cell.pass_turnover is False
    assert cell.turnover_increase_pct == pytest.approx(25.0)
    assert cell.all_pass is False


def test_evaluate_retune_gate_no_cell_qualifies_across_full_grid() -> None:
    # Two cells, both fail at least one gate.
    rows = _three_window_baselines() + [
        # cell A — only +0.5% uplift, fails gate 1
        _cell_row(
            cadence=CADENCE_MONTHLY, vol_target=0.09, window=_CALM,
            ending_value=100_500.0, gap_vs_60_40=-9_500.0,
            max_drawdown=-0.20, turnover=2.00,
        ),
        _cell_row(
            cadence=CADENCE_MONTHLY, vol_target=0.09, window=_STRESS_1,
            ending_value=95_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.14, turnover=1.00,
        ),
        _cell_row(
            cadence=CADENCE_MONTHLY, vol_target=0.09, window=_STRESS_2,
            ending_value=99_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.09, turnover=1.00,
        ),
        # cell B — turnover increase 30% (fails gate 4) and DD harm (fails gate 3)
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.13, window=_CALM,
            ending_value=108_000.0, gap_vs_60_40=-2_000.0,
            max_drawdown=-0.20, turnover=2.60,
        ),
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.13, window=_STRESS_1,
            ending_value=90_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.18, turnover=1.30,
        ),
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.13, window=_STRESS_2,
            ending_value=98_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.05, turnover=1.30,
        ),
    ]

    verdict = evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )

    assert verdict.gate_met is False
    assert verdict.winning_cell is None
    assert len(verdict.cells) == 2
    assert all(cell.all_pass is False for cell in verdict.cells)


def test_evaluate_retune_gate_picks_winner_by_highest_calm_ending_then_stress2_dd() -> None:
    # Two passing cells. Cell A has higher calm ending value; Cell B ties
    # baseline calm uplift but loses on the primary criterion. Winner = A.
    cell_a = (CADENCE_QUARTERLY, 0.10)
    cell_b = (CADENCE_MONTHLY, 0.11)
    rows = _three_window_baselines()
    candidates = (
        (cell_a[0], cell_a[1], 108_000.0),
        (cell_b[0], cell_b[1], 105_000.0),
    )
    for cadence, vt, end_calm in candidates:
        rows.extend([
            _cell_row(
                cadence=cadence, vol_target=vt, window=_CALM,
                ending_value=end_calm, gap_vs_60_40=end_calm - 110_000.0,
                max_drawdown=-0.20, turnover=2.05,
            ),
            _cell_row(
                cadence=cadence, vol_target=vt, window=_STRESS_1,
                ending_value=96_000.0, gap_vs_60_40=0.0,
                max_drawdown=-0.10, turnover=1.00,
            ),
            _cell_row(
                cadence=cadence, vol_target=vt, window=_STRESS_2,
                ending_value=100_000.0, gap_vs_60_40=0.0,
                max_drawdown=-0.05, turnover=1.00,
            ),
        ])

    verdict = evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )

    assert verdict.gate_met is True
    assert verdict.winning_cell == cell_a


def test_evaluate_retune_gate_is_deterministic_across_runs() -> None:
    rows = _three_window_baselines() + [
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.10, window=_CALM,
            ending_value=106_000.0, gap_vs_60_40=-4_000.0,
            max_drawdown=-0.20, turnover=2.05,
        ),
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.10, window=_STRESS_1,
            ending_value=96_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.10, turnover=1.00,
        ),
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.10, window=_STRESS_2,
            ending_value=100_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.05, turnover=1.00,
        ),
        _cell_row(
            cadence=CADENCE_MONTHLY, vol_target=0.11, window=_CALM,
            ending_value=104_000.0, gap_vs_60_40=-6_000.0,
            max_drawdown=-0.20, turnover=2.10,
        ),
        _cell_row(
            cadence=CADENCE_MONTHLY, vol_target=0.11, window=_STRESS_1,
            ending_value=95_500.0, gap_vs_60_40=0.0,
            max_drawdown=-0.12, turnover=1.05,
        ),
        _cell_row(
            cadence=CADENCE_MONTHLY, vol_target=0.11, window=_STRESS_2,
            ending_value=99_500.0, gap_vs_60_40=0.0,
            max_drawdown=-0.08, turnover=1.05,
        ),
    ]

    first = evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )
    second = evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )

    assert first == second
    # Defensive: explicit byte-equivalent repr check (frozen dataclasses
    # have stable __repr__ and equality is field-wise).
    assert repr(first) == repr(second)


def test_evaluate_retune_gate_does_not_mutate_strategy_defaults() -> None:
    rows = _three_window_baselines() + [
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.10, window=_CALM,
            ending_value=106_000.0, gap_vs_60_40=-4_000.0,
            max_drawdown=-0.20, turnover=2.05,
        ),
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.10, window=_STRESS_1,
            ending_value=96_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.10, turnover=1.00,
        ),
        _cell_row(
            cadence=CADENCE_QUARTERLY, vol_target=0.10, window=_STRESS_2,
            ending_value=100_000.0, gap_vs_60_40=0.0,
            max_drawdown=-0.05, turnover=1.00,
        ),
    ]

    pre_b010 = RiskParityParameters()
    pre_b013 = RegimeAdaptiveConfig()
    evaluate_retune_gate(
        rows,
        _STRATEGY,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
    )
    post_b010 = RiskParityParameters()
    post_b013 = RegimeAdaptiveConfig()

    assert post_b010 == pre_b010
    assert post_b013.target_volatility == pre_b013.target_volatility


def test_evaluate_retune_gate_rejects_unknown_strategy() -> None:
    with pytest.raises(ValueError, match="unknown strategy"):
        evaluate_retune_gate(
            (),
            "b099",
            calm_window=_CALM,
            stress_windows=(_STRESS_1, _STRESS_2),
        )


def test_default_gate_constant_matches_spec() -> None:
    assert isinstance(DEFAULT_GATE, RetuneGate)
    assert DEFAULT_GATE.min_calm_uplift_pct == 1.0
    assert DEFAULT_GATE.min_calm_gap_narrowing_pp == 5.0
    assert DEFAULT_GATE.do_no_harm_on_stress is True
    assert DEFAULT_GATE.max_turnover_increase_pct == 15.0


def test_retune_gate_verdict_dataclass_is_frozen() -> None:
    cell = CellGateVerdict(
        cadence=CADENCE_QUARTERLY,
        vol_target=0.10,
        calm_ending_value=106_000.0,
        baseline_calm_ending_value=100_000.0,
        calm_uplift_pct=6.0,
        calm_gap_narrowing_pp=6.0,
        stress_max_dd_deltas=((_STRESS_1, 0.05), (_STRESS_2, 0.05)),
        calm_turnover=2.05,
        baseline_calm_turnover=2.00,
        turnover_increase_pct=2.5,
        pass_calm_uplift=True,
        pass_calm_gap_narrowing=True,
        pass_stress_do_no_harm=True,
        pass_turnover=True,
        all_pass=True,
    )
    verdict = RetuneGateVerdict(
        strategy=_STRATEGY,
        gate=DEFAULT_GATE,
        default_cadence=_DEFAULT_CADENCE,
        default_vol_target=_DEFAULT_VT,
        calm_window=_CALM,
        stress_windows=(_STRESS_1, _STRESS_2),
        cells=(cell,),
        gate_met=True,
        winning_cell=(CADENCE_QUARTERLY, 0.10),
    )
    with pytest.raises((AttributeError, TypeError, FrozenInstanceError)):
        verdict.gate_met = False  # type: ignore[misc]
