from datetime import date
from pathlib import Path

from trade.data.loader import DataSnapshot, PriceBar, load_fixture_prices
from trade.data.quality import evaluate_data_quality


def test_default_fixture_reports_quality_flags_and_limitations() -> None:
    report = evaluate_data_quality(load_fixture_prices())

    assert "trading_calendar_gap:2024-02-29..2024-04-30" in report.quality_flags
    assert any(
        flag.startswith("suspicious_adjusted_close_jump:SPY")
        for flag in report.quality_flags
    )
    assert "not_point_in_time_production_data" in report.research_limitations
    assert any("not_live_trading_ready" in item for item in report.research_limitations)


def test_research_sample_reports_sample_source_limitation() -> None:
    snapshot = load_fixture_prices(Path("trade/data/fixtures/research_sample_prices.json"))
    report = evaluate_data_quality(snapshot)

    assert "sample_data_source:synthetic-research-sample-v1" in report.research_limitations
    assert "optional_public_best_effort_non_pit" in report.research_limitations


def test_imported_snapshot_reports_public_research_limitations() -> None:
    snapshot = DataSnapshot(
        records=(
            PriceBar(
                date=date(2024, 1, 31),
                symbol="SPY",
                open=100.0,
                close=101.0,
                adjusted_close=101.0,
                volume=1000,
            ),
        ),
        source="manual-public-data-import",
        adjusted_price_policy="public_best_effort_adjusted_close",
        data_snapshot_id="snapshot:abc123",
        checksum="a" * 64,
        start_date=date(2024, 1, 31),
        end_date=date(2024, 1, 31),
        symbols=("SPY",),
        trading_calendar_gaps=("2024-01-31..2024-03-29",),
    )

    report = evaluate_data_quality(snapshot)

    assert "trading_calendar_gap:2024-01-31..2024-03-29" in report.quality_flags
    assert "imported_snapshot_data" in report.research_limitations
    assert "public-best-effort" in report.research_limitations
    assert "non-PIT" in report.research_limitations
    assert "research-only" in report.research_limitations
    assert "not-live-trading-ready" in report.research_limitations
