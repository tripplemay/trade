"""B016 F004 — comparative HRP-vs-inverse-vol harness + report.

Covers:

- Run semantics: harness runs both weighting methods on the same fixture and
  emits a serialisable payload with the required schema sections.
- Skipped semantics: when the B014 manifest is absent,
  ``try_run_real_snapshot_hrp_comparison`` returns a ``skipped`` result with
  no method rows; the report builder still emits a valid payload.
- Fixture-manifest stub semantics: writing a tiny manifest + per-ticker CSVs
  to disk allows the snapshot loader to drive the harness end-to-end and the
  report's ``real_data_status.status`` becomes ``ran``.
- Static 60/40 baseline loader is robust to missing / malformed sidecar.
- Markdown rendering reflects both ran and skipped narrative branches.
"""

from __future__ import annotations

import csv
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from trade.backtest.monthly import BacktestParameters
from trade.data.loader import PriceBar
from trade.strategies.risk_parity import RiskParityParameters
from trade.strategies.risk_parity_hrp_comparison import (
    COMPARISON_STATUS_RAN,
    COMPARISON_STATUS_SKIPPED,
    NARRATIVE_GAP_SHRUNK,
    NARRATIVE_REAL_DATA_RAN,
    NARRATIVE_REAL_DATA_SKIPPED,
    ORDERED_METHODS,
    RESEARCH_ONLY_DISCLAIMER,
    HRPComparisonResult,
    build_hrp_comparison_payload,
    build_monthly_signal_dates,
    generate_hrp_comparison_report,
    load_static_60_40_baseline,
    render_hrp_comparison_markdown,
    run_hrp_comparison,
    try_run_real_snapshot_hrp_comparison,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

_NINE_ASSETS: tuple[str, ...] = (
    "SPY",
    "VEA",
    "VWO",
    "AGG",
    "IEF",
    "GLD",
    "VNQ",
    "DBC",
    "SGOV",
)


def _amplitude(symbol: str, index: int) -> float:
    return {
        "SPY": 0.018,
        "VEA": 0.020,
        "VWO": 0.025,
        "AGG": 0.006,
        "IEF": 0.007,
        "GLD": 0.012,
        "VNQ": 0.022,
        "DBC": 0.024,
        "SGOV": 0.0008,
    }.get(symbol, 0.010 + 0.001 * index)


def _phase(symbol: str) -> int:
    return {
        "SPY": 0,
        "VEA": 0,
        "VWO": 0,
        "AGG": 1,
        "IEF": 1,
        "GLD": 0,
        "VNQ": 0,
        "DBC": 1,
        "SGOV": 0,
    }.get(symbol, 0)


def _nine_asset_records(observations: int = 200) -> tuple[PriceBar, ...]:
    start = date(2024, 1, 1)
    bars: list[PriceBar] = []
    for index, symbol in enumerate(_NINE_ASSETS):
        price = 100.0 + index
        amp = _amplitude(symbol, index)
        phase = _phase(symbol)
        for day in range(observations):
            if day:
                step = amp if (day + phase) % 2 == 0 else -amp * 0.95
                price *= 1.0 + step
            bars.append(
                PriceBar(
                    date=start + timedelta(days=day),
                    symbol=symbol,
                    open=price * 0.999,
                    close=price,
                    adjusted_close=price,
                    volume=1_000,
                )
            )
    return tuple(bars)


def _template(volatility_lookback: int = 60) -> RiskParityParameters:
    return RiskParityParameters(
        universe=_NINE_ASSETS,
        volatility_lookback=volatility_lookback,
        defensive_asset="SGOV",
        target_volatility=1.0,
        max_asset_weight=1.0,
    )


def _monthly_dates(records: tuple[PriceBar, ...], start: date, end: date) -> tuple[date, ...]:
    trading_dates = tuple(sorted({record.date for record in records}))
    return build_monthly_signal_dates(trading_dates, start, end)


# --------------------------------------------------------------------------- #
# Harness — run semantics
# --------------------------------------------------------------------------- #


def test_harness_runs_both_methods_on_synthetic_universe() -> None:
    records = _nine_asset_records()
    signal_dates = _monthly_dates(records, date(2024, 4, 1), date(2024, 7, 1))
    assert len(signal_dates) >= 2

    comparison = run_hrp_comparison(records, signal_dates, _template())

    assert comparison.snapshot_status == COMPARISON_STATUS_RAN
    assert tuple(row.method for row in comparison.method_rows) == ORDERED_METHODS
    for row in comparison.method_rows:
        assert row.rebalance_count == len(signal_dates)
        assert row.ending_value > 0
        assert len(row.weight_history) == len(signal_dates)
        assert "2020_q1_q4" in row.stress_window_max_drawdowns
        assert "2022_full_year" in row.stress_window_max_drawdowns


def test_harness_run_records_per_method_weight_history() -> None:
    records = _nine_asset_records()
    signal_dates = _monthly_dates(records, date(2024, 4, 1), date(2024, 7, 1))

    comparison = run_hrp_comparison(records, signal_dates, _template())

    for row in comparison.method_rows:
        signal_dates_seen = [iso for iso, _ in row.weight_history]
        expected = [d.isoformat() for d in signal_dates]
        assert signal_dates_seen == expected
        for _, weights in row.weight_history:
            total = sum(weights.values())
            assert abs(total - 1.0) < 1e-8


def test_harness_run_methods_diverge_on_realistic_fixture() -> None:
    records = _nine_asset_records()
    signal_dates = _monthly_dates(records, date(2024, 4, 1), date(2024, 7, 1))

    comparison = run_hrp_comparison(records, signal_dates, _template())

    rows = {row.method: row for row in comparison.method_rows}
    inverse_vol = rows["inverse_volatility"]
    hrp = rows["hrp"]
    assert inverse_vol.ending_value != hrp.ending_value


# --------------------------------------------------------------------------- #
# Skipped semantics
# --------------------------------------------------------------------------- #


def test_try_real_snapshot_returns_skipped_when_manifest_missing(tmp_path: Path) -> None:
    missing_manifest = tmp_path / "missing.json"

    comparison = try_run_real_snapshot_hrp_comparison(missing_manifest, _template())

    assert comparison.snapshot_status == COMPARISON_STATUS_SKIPPED
    assert comparison.snapshot_reason is not None
    assert "manifest not found" in comparison.snapshot_reason
    assert comparison.method_rows == ()
    assert comparison.snapshot_manifest_id is None
    assert comparison.snapshot_date_range is None


def test_report_payload_emits_skipped_status_and_narrative_skipped_note(
    tmp_path: Path,
) -> None:
    comparison = try_run_real_snapshot_hrp_comparison(
        tmp_path / "missing.json", _template()
    )

    payload = build_hrp_comparison_payload(
        comparison,
        baseline_60_40={},
        run_id="B016-rp-hrp-comparison-test",
        report_date=date(2026, 5, 14),
    )

    assert payload["real_data_status"]["status"] == COMPARISON_STATUS_SKIPPED  # type: ignore[index]
    assert payload["narrative"]["status"] == NARRATIVE_REAL_DATA_SKIPPED  # type: ignore[index]
    assert payload["hrp_comparison"]["method_rows"] == []  # type: ignore[index]
    assert (
        RESEARCH_ONLY_DISCLAIMER
        in payload["research_limitations"]["disclaimer"]  # type: ignore[index]
    )


# --------------------------------------------------------------------------- #
# Fixture-manifest stub: run semantics through the snapshot loader
# --------------------------------------------------------------------------- #


def _write_fixture_manifest(tmp_path: Path) -> Path:
    """Build a tiny B014-style manifest + CSVs so the loader can run end-to-end."""

    csv_dir = tmp_path / "csvs"
    csv_dir.mkdir(parents=True, exist_ok=True)
    manifest_files: list[dict[str, str]] = []
    for symbol in _NINE_ASSETS:
        csv_path = csv_dir / f"{symbol}.csv"
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["date", "open", "close", "adjusted_close", "volume"],
            )
            writer.writeheader()
            amp = _amplitude(symbol, 0)
            phase = _phase(symbol)
            price = 100.0
            current = date(2024, 1, 1)
            for day in range(200):
                if day:
                    step = amp if (day + phase) % 2 == 0 else -amp * 0.95
                    price *= 1.0 + step
                writer.writerow(
                    {
                        "date": current.isoformat(),
                        "open": price * 0.999,
                        "close": price,
                        "adjusted_close": price,
                        "volume": 1000,
                    }
                )
                current += timedelta(days=1)
        manifest_files.append({"ticker": symbol, "path": csv_path.name})
    manifest_path = csv_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "snapshot_id": "fixture-stub-snapshot",
                "files": manifest_files,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return manifest_path


def test_try_real_snapshot_runs_when_fixture_manifest_present(tmp_path: Path) -> None:
    manifest_path = _write_fixture_manifest(tmp_path)

    comparison = try_run_real_snapshot_hrp_comparison(
        manifest_path,
        _template(volatility_lookback=60),
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        window_start=date(2024, 4, 1),
        window_end=date(2024, 7, 1),
    )

    assert comparison.snapshot_status == COMPARISON_STATUS_RAN
    assert comparison.snapshot_manifest_id == "fixture-stub-snapshot"
    assert comparison.snapshot_date_range is not None
    assert len(comparison.method_rows) == 2
    for row in comparison.method_rows:
        assert row.rebalance_count > 0
        assert row.ending_value > 0


def test_generate_report_writes_json_and_markdown_artifacts(tmp_path: Path) -> None:
    manifest_path = _write_fixture_manifest(tmp_path / "manifest")
    output_dir = tmp_path / "report"

    comparison = try_run_real_snapshot_hrp_comparison(
        manifest_path,
        _template(volatility_lookback=60),
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
        window_start=date(2024, 4, 1),
        window_end=date(2024, 7, 1),
    )
    baseline = {
        "CAGR": 0.05,
        "Sharpe": 0.4,
        "annualized_volatility": 0.12,
        "ending_value": 100_500.0,
        "max_drawdown": -0.05,
    }
    artifacts = generate_hrp_comparison_report(
        comparison,
        baseline_60_40=baseline,
        output_dir=output_dir,
        run_id="B016-test-hrp-comparison",
        report_date=date(2026, 5, 14),
    )

    assert artifacts.json_path.is_file()
    assert artifacts.markdown_path.is_file()
    payload = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert payload["run"]["run_id"] == "B016-test-hrp-comparison"
    assert payload["real_data_status"]["status"] == COMPARISON_STATUS_RAN
    methods_in_payload = [row["method"] for row in payload["hrp_comparison"]["method_rows"]]
    assert methods_in_payload == list(ORDERED_METHODS)
    assert payload["baselines"]["static_60_40"]["ending_value"] == 100_500.0
    assert payload["narrative"]["status"] in (
        NARRATIVE_REAL_DATA_RAN,
        NARRATIVE_REAL_DATA_SKIPPED,
    )
    markdown = artifacts.markdown_path.read_text(encoding="utf-8")
    assert "## Per-Method Metrics" in markdown
    assert "inverse_volatility" in markdown
    assert "hrp" in markdown
    assert RESEARCH_ONLY_DISCLAIMER in markdown


# --------------------------------------------------------------------------- #
# Narrative — verdict computed when baseline + both methods present
# --------------------------------------------------------------------------- #


def test_narrative_status_ran_when_baseline_and_methods_present() -> None:
    records = _nine_asset_records()
    signal_dates = _monthly_dates(records, date(2024, 4, 1), date(2024, 7, 1))
    comparison = run_hrp_comparison(records, signal_dates, _template())

    baseline = {"ending_value": 110_000.0}
    payload = build_hrp_comparison_payload(
        comparison,
        baseline_60_40=baseline,
        run_id="B016-rp-hrp-comparison-narrative",
        report_date=date(2026, 5, 14),
    )

    narrative = payload["narrative"]
    assert isinstance(narrative, dict)
    assert narrative["status"] == NARRATIVE_REAL_DATA_RAN
    assert "verdict" in narrative
    assert "inverse_volatility_gap_vs_60_40" in narrative
    assert "hrp_gap_vs_60_40" in narrative


def test_narrative_verdict_shrunk_when_hrp_closer_to_baseline() -> None:
    inverse_vol_ending = 90_000.0
    hrp_ending = 95_000.0
    baseline_ending = 105_000.0
    # inverse_vol_gap = 15_000, hrp_gap = 10_000, delta = +5_000 → shrunk.
    method_rows = (
        _make_method_row("inverse_volatility", ending=inverse_vol_ending),
        _make_method_row("hrp", ending=hrp_ending),
    )
    comparison = HRPComparisonResult(
        snapshot_status=COMPARISON_STATUS_RAN,
        snapshot_reason=None,
        snapshot_manifest_id="stub",
        snapshot_date_range=(date(2020, 6, 30), date(2022, 12, 31)),
        starting_capital=100_000.0,
        universe=_NINE_ASSETS,
        stress_windows=(),
        method_rows=method_rows,
    )
    payload = build_hrp_comparison_payload(
        comparison,
        baseline_60_40={"ending_value": baseline_ending},
        run_id="B016-rp-hrp-verdict",
        report_date=date(2026, 5, 14),
    )

    assert payload["narrative"]["verdict"] == NARRATIVE_GAP_SHRUNK  # type: ignore[index]


# --------------------------------------------------------------------------- #
# Static 60/40 baseline loader
# --------------------------------------------------------------------------- #


def test_load_static_60_40_baseline_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_static_60_40_baseline(tmp_path / "missing.json") == {}


def test_load_static_60_40_baseline_returns_empty_on_malformed_json(
    tmp_path: Path,
) -> None:
    path = tmp_path / "bad.json"
    path.write_text("not-json", encoding="utf-8")

    assert load_static_60_40_baseline(path) == {}


def test_load_static_60_40_baseline_strips_equity_curve(tmp_path: Path) -> None:
    path = tmp_path / "sidecar.json"
    path.write_text(
        json.dumps(
            {
                "comparison": {
                    "strategies": {
                        "static_60_40": {
                            "ending_value": 123_456.78,
                            "CAGR": 0.07,
                            "equity_curve": [{"date": "2020-06-30", "value": 100_000.0}],
                        },
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    baseline = load_static_60_40_baseline(path)

    assert baseline["ending_value"] == 123_456.78
    assert baseline["CAGR"] == 0.07
    assert "equity_curve" not in baseline


# --------------------------------------------------------------------------- #
# Markdown rendering
# --------------------------------------------------------------------------- #


def test_markdown_includes_disclaimer_and_required_sections() -> None:
    records = _nine_asset_records()
    signal_dates = _monthly_dates(records, date(2024, 4, 1), date(2024, 7, 1))
    comparison = run_hrp_comparison(records, signal_dates, _template())

    payload = build_hrp_comparison_payload(
        comparison,
        baseline_60_40={"ending_value": 100_000.0, "CAGR": 0.05},
        run_id="B016-rp-hrp-md-test",
        report_date=date(2026, 5, 14),
    )
    markdown = render_hrp_comparison_markdown(payload)

    for heading in (
        "## Summary",
        "## Real-Data Status",
        "## Per-Method Metrics",
        "## Stress Window Verdict Per Method",
        "## Static 60/40 Baseline",
        "## Narrative",
        "## Research Limitations",
    ):
        assert heading in markdown, f"Missing heading: {heading}"
    assert RESEARCH_ONLY_DISCLAIMER in markdown
    # No paper/live execution phrasing in the rendered markdown.
    forbidden = ("paper-execution", "live execution", "executed-order", "place_order")
    lowered = markdown.lower()
    for term in forbidden:
        assert term not in lowered


def test_markdown_skipped_narrative_reports_skipped_note(tmp_path: Path) -> None:
    comparison = try_run_real_snapshot_hrp_comparison(
        tmp_path / "missing.json", _template()
    )
    payload = build_hrp_comparison_payload(
        comparison,
        baseline_60_40={},
        run_id="B016-rp-hrp-md-skipped",
        report_date=date(2026, 5, 14),
    )
    markdown = render_hrp_comparison_markdown(payload)

    assert "Status: skipped" in markdown
    assert NARRATIVE_REAL_DATA_SKIPPED in markdown


# --------------------------------------------------------------------------- #
# Helpers used by narrative-verdict test
# --------------------------------------------------------------------------- #


def _make_method_row(method: str, *, ending: float) -> object:
    from trade.strategies.risk_parity_hrp_comparison import HRPMethodRow

    return HRPMethodRow(
        method=method,
        annualized_return=0.0,
        annualized_volatility=0.0,
        sharpe=0.0,
        max_drawdown=0.0,
        turnover=0.0,
        rebalance_count=0,
        stress_window_max_drawdowns={},
        stress_window_status={},
        ending_value=ending,
        cost_amount=0.0,
        weight_history=(),
    )


# --------------------------------------------------------------------------- #
# Argument guard: unknown weighting_method on the template would already raise
# in __post_init__; this is a sanity check that the harness preserves it.
# --------------------------------------------------------------------------- #


def test_template_with_invalid_weighting_method_rejected_at_construction() -> None:
    with pytest.raises(Exception, match="weighting_method"):
        RiskParityParameters(
            universe=_NINE_ASSETS,
            volatility_lookback=60,
            defensive_asset="SGOV",
            weighting_method="bogus",  # type: ignore[arg-type]
        )
