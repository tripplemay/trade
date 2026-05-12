import json
from pathlib import Path

import pytest

from trade.data.loader import FixtureDataError, load_fixture_prices


def test_default_fixture_loads_without_external_inputs() -> None:
    snapshot = load_fixture_prices()

    assert snapshot.source == "synthetic-global-etf-fixture-v1"
    assert snapshot.symbols == ("AGG", "EEM", "SPY", "VEA")
    assert snapshot.start_date.isoformat() == "2024-01-31"
    assert snapshot.end_date.isoformat() == "2024-12-31"
    assert snapshot.data_snapshot_id.startswith("fixture:")
    assert len(snapshot.checksum) == 64


def test_fixture_reports_trading_calendar_gap() -> None:
    snapshot = load_fixture_prices()

    assert snapshot.trading_calendar_gaps == ("2024-02-29..2024-04-30",)


def test_fixture_preserves_adjusted_close_separately_from_close() -> None:
    snapshot = load_fixture_prices()

    split_record = next(
        record
        for record in snapshot.records
        if record.date.isoformat() == "2024-04-30" and record.symbol == "SPY"
    )

    assert split_record.close == 107.0
    assert split_record.adjusted_close == 53.5


def test_snapshot_metadata_is_reproducible() -> None:
    first = load_fixture_prices()
    second = load_fixture_prices()

    assert first.data_snapshot_id == second.data_snapshot_id
    assert first.checksum == second.checksum
    assert first.records == second.records


def test_missing_value_fails_schema_validation(tmp_path: Path) -> None:
    fixture_path = tmp_path / "bad_fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "source": "bad",
                "adjusted_price_policy": "adjusted",
                "records": [
                    {
                        "date": "2024-01-31",
                        "symbol": "SPY",
                        "open": 100.0,
                        "close": 101.0,
                        "adjusted_close": None,
                        "volume": 100,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(FixtureDataError, match="adjusted_close"):
        load_fixture_prices(fixture_path)
