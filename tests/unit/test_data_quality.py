from pathlib import Path

from trade.data.loader import load_fixture_prices
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
