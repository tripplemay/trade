import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.strategies.regime_adaptive.snapshot import (
    DEFAULT_SHORT_HISTORY_ALLOWANCE,
    DEFAULT_START_TOLERANCE_BUSINESS_DAYS,
    REGIME_ADAPTIVE_SNAPSHOT_FILENAME_PREFIX,
    REGIME_ADAPTIVE_SNAPSHOT_MANIFEST_NAME,
    REQUIRED_TICKERS,
    RegimeAdaptiveSnapshotError,
    RegimeAdaptiveSnapshotRequest,
    RegimeAdaptiveSnapshotResult,
    import_regime_adaptive_snapshot,
)


def _write_csv(path: Path, symbol: str, start: date, end: date) -> None:
    rows = ["date,open,high,low,close,adjusted_close,volume"]
    current = start
    price = 100.0
    while current <= end:
        # only weekdays to mimic public OHLCV files
        if current.weekday() < 5:
            high = price + 0.5
            low = price - 0.5
            rows.append(
                f"{current.isoformat()},{price:.4f},{high:.4f},{low:.4f},"
                f"{price:.4f},{price:.4f},1000"
            )
            price += 0.05
        current += timedelta(days=1)
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def _write_full_universe(source_dir: Path, start: date, end: date) -> None:
    source_dir.mkdir(parents=True, exist_ok=True)
    for symbol in REQUIRED_TICKERS:
        _write_csv(source_dir / f"{symbol}.csv", symbol, start, end)


def test_required_tickers_cover_regime_adaptive_universe() -> None:
    assert REQUIRED_TICKERS == ("SPY", "QQQ", "VEA", "VWO", "IEF", "TLT", "GLD", "DBC", "SGOV")


def test_import_regime_adaptive_snapshot_writes_manifest_and_per_ticker_files(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_full_universe(source_dir, date(2018, 1, 1), date(2025, 12, 31))

    result = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=source_dir,
            output_dir=output_dir,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    assert isinstance(result, RegimeAdaptiveSnapshotResult)
    assert result.manifest_file.exists()
    assert result.manifest_file.name == REGIME_ADAPTIVE_SNAPSHOT_MANIFEST_NAME
    for ticker, ticker_path in result.ticker_files.items():
        assert ticker in REQUIRED_TICKERS
        assert ticker_path.exists()
        assert ticker_path.name.startswith(REGIME_ADAPTIVE_SNAPSHOT_FILENAME_PREFIX)
        assert ticker in ticker_path.name


def test_import_regime_adaptive_snapshot_manifest_schema(tmp_path: Path) -> None:
    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_full_universe(source_dir, date(2018, 1, 1), date(2025, 12, 31))

    result = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=source_dir,
            output_dir=output_dir,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )
    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))

    assert manifest["snapshot_id"] == result.snapshot_id
    assert manifest["source"] == "regime-adaptive-public-import"
    assert manifest["tickers"] == list(REQUIRED_TICKERS)
    assert manifest["date_range"]["start"] == "2018-01-01"
    assert manifest["date_range"]["end"] == "2025-12-31"
    assert len(manifest["files"]) == len(REQUIRED_TICKERS)
    for file_entry in manifest["files"]:
        assert "ticker" in file_entry
        assert "path" in file_entry
        assert "sha256" in file_entry
    assert "research-only" in manifest["limitations"]["disclaimer"].lower()


def test_import_regime_adaptive_snapshot_id_is_deterministic_across_runs(
    tmp_path: Path,
) -> None:
    first_source = tmp_path / "raw-1"
    second_source = tmp_path / "raw-2"
    first_output = tmp_path / "public-cache-1"
    second_output = tmp_path / "public-cache-2"
    _write_full_universe(first_source, date(2018, 1, 1), date(2025, 12, 31))
    _write_full_universe(second_source, date(2018, 1, 1), date(2025, 12, 31))

    first = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=first_source,
            output_dir=first_output,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )
    second = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=second_source,
            output_dir=second_output,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    assert first.snapshot_id == second.snapshot_id


def test_import_regime_adaptive_snapshot_fails_closed_on_missing_ticker(tmp_path: Path) -> None:
    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_full_universe(source_dir, date(2018, 1, 1), date(2025, 12, 31))
    (source_dir / "TLT.csv").unlink()

    with pytest.raises(RegimeAdaptiveSnapshotError, match="TLT"):
        import_regime_adaptive_snapshot(
            RegimeAdaptiveSnapshotRequest(
                source_dir=source_dir,
                output_dir=output_dir,
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_import_regime_adaptive_snapshot_fails_closed_without_manual_confirmation(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_full_universe(source_dir, date(2018, 1, 1), date(2025, 12, 31))

    with pytest.raises(RegimeAdaptiveSnapshotError, match="manual confirmation"):
        import_regime_adaptive_snapshot(
            RegimeAdaptiveSnapshotRequest(
                source_dir=source_dir,
                output_dir=output_dir,
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=False,
            )
        )


def test_import_regime_adaptive_snapshot_fails_closed_on_insufficient_date_coverage(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_full_universe(source_dir, date(2020, 1, 1), date(2024, 12, 31))

    with pytest.raises(RegimeAdaptiveSnapshotError, match="date_range"):
        import_regime_adaptive_snapshot(
            RegimeAdaptiveSnapshotRequest(
                source_dir=source_dir,
                output_dir=output_dir,
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_import_regime_adaptive_snapshot_fails_closed_on_source_dir_missing(
    tmp_path: Path,
) -> None:
    with pytest.raises(RegimeAdaptiveSnapshotError, match="source_dir"):
        import_regime_adaptive_snapshot(
            RegimeAdaptiveSnapshotRequest(
                source_dir=tmp_path / "missing",
                output_dir=tmp_path / "public-cache",
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_import_regime_adaptive_snapshot_does_not_touch_socket(
    tmp_path: Path, monkeypatch: Any
) -> None:
    """A successful import must never open a socket."""

    def _refuse_socket(*args: object, **kwargs: object) -> None:
        raise RuntimeError("network access is not allowed during snapshot import")

    monkeypatch.setattr("socket.socket", _refuse_socket)

    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_full_universe(source_dir, date(2018, 1, 1), date(2025, 12, 31))

    result = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=source_dir,
            output_dir=output_dir,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )
    assert result.manifest_file.exists()


def test_default_short_history_allowance_covers_sgov() -> None:
    assert frozenset({"SGOV"}) == DEFAULT_SHORT_HISTORY_ALLOWANCE
    assert DEFAULT_START_TOLERANCE_BUSINESS_DAYS == 5


def _write_universe_with_overrides(
    source_dir: Path,
    default_start: date,
    default_end: date,
    *,
    overrides: dict[str, tuple[date, date]] | None = None,
) -> None:
    """Write the full 9-ticker universe with per-ticker date overrides."""

    source_dir.mkdir(parents=True, exist_ok=True)
    overrides = overrides or {}
    for symbol in REQUIRED_TICKERS:
        start, end = overrides.get(symbol, (default_start, default_end))
        _write_csv(source_dir / f"{symbol}.csv", symbol, start, end)


def test_import_accepts_first_trading_day_start_within_tolerance(tmp_path: Path) -> None:
    """A holiday at the very start of the window must not block acquisition.

    2018-01-01 was a NYSE holiday; SPY's first trading day was 2018-01-02 (a Tuesday).
    The default 5-business-day tolerance must accept that one-day shortfall.
    """

    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_universe_with_overrides(source_dir, date(2018, 1, 2), date(2025, 12, 31))

    result = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=source_dir,
            output_dir=output_dir,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    assert result.manifest_file.exists()
    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))
    for file_entry in manifest["files"]:
        assert file_entry["short_history_exempt"] is False, (
            f"{file_entry['ticker']} should not be flagged short-history exempt under "
            "first-trading-day tolerance"
        )


def test_import_rejects_excessive_start_gap_for_full_history_ticker(
    tmp_path: Path,
) -> None:
    """Ten-business-day shortfall for a full-history ticker must still fail closed."""

    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    # 2018-01-15 is 10 business days after 2018-01-01; exceeds the default tolerance of 5.
    _write_universe_with_overrides(source_dir, date(2018, 1, 15), date(2025, 12, 31))

    with pytest.raises(RegimeAdaptiveSnapshotError, match="business days after required"):
        import_regime_adaptive_snapshot(
            RegimeAdaptiveSnapshotRequest(
                source_dir=source_dir,
                output_dir=output_dir,
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
            )
        )


def test_import_accepts_short_history_sgov_with_late_inception(tmp_path: Path) -> None:
    """Real yfinance SGOV first-available date is 2020-06-01 (after our hardcoded
    2020-05-28 inception). The default SGOV allowance must let this through and the
    manifest must flag SGOV as short-history exempt while leaving the other 8 tickers
    flagged as not exempt."""

    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_universe_with_overrides(
        source_dir,
        default_start=date(2018, 1, 1),
        default_end=date(2025, 12, 31),
        overrides={"SGOV": (date(2020, 6, 1), date(2025, 12, 31))},
    )

    result = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=source_dir,
            output_dir=output_dir,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))
    short_history_flags = {
        entry["ticker"]: entry["short_history_exempt"] for entry in manifest["files"]
    }
    assert short_history_flags["SGOV"] is True
    for ticker in REQUIRED_TICKERS:
        if ticker != "SGOV":
            assert short_history_flags[ticker] is False, (
                f"{ticker} is not in the short-history allowance and must not be flagged exempt"
            )
    sgov_entry = next(entry for entry in manifest["files"] if entry["ticker"] == "SGOV")
    assert sgov_entry["start"] == "2020-06-01"


def test_import_rejects_short_history_ticker_when_allowance_disabled(
    tmp_path: Path,
) -> None:
    """With short-history allowance explicitly disabled, SGOV's 2020-06 start fails."""

    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_universe_with_overrides(
        source_dir,
        default_start=date(2018, 1, 1),
        default_end=date(2025, 12, 31),
        overrides={"SGOV": (date(2020, 6, 1), date(2025, 12, 31))},
    )

    with pytest.raises(RegimeAdaptiveSnapshotError, match="SGOV"):
        import_regime_adaptive_snapshot(
            RegimeAdaptiveSnapshotRequest(
                source_dir=source_dir,
                output_dir=output_dir,
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
                allow_short_history=frozenset(),
            )
        )


def test_import_rejects_negative_start_tolerance(tmp_path: Path) -> None:
    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_universe_with_overrides(source_dir, date(2018, 1, 1), date(2025, 12, 31))

    with pytest.raises(
        RegimeAdaptiveSnapshotError, match="start_tolerance_business_days"
    ):
        import_regime_adaptive_snapshot(
            RegimeAdaptiveSnapshotRequest(
                source_dir=source_dir,
                output_dir=output_dir,
                date_from=date(2018, 1, 1),
                date_to=date(2025, 12, 31),
                manual_confirmation=True,
                start_tolerance_business_days=-1,
            )
        )


def test_manifest_files_include_short_history_exempt_field(tmp_path: Path) -> None:
    source_dir = tmp_path / "raw"
    output_dir = tmp_path / "public-cache"
    _write_full_universe(source_dir, date(2018, 1, 1), date(2025, 12, 31))

    result = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=source_dir,
            output_dir=output_dir,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )

    manifest = json.loads(result.manifest_file.read_text(encoding="utf-8"))
    for file_entry in manifest["files"]:
        assert "short_history_exempt" in file_entry
        assert isinstance(file_entry["short_history_exempt"], bool)


def test_snapshot_id_is_stable_across_short_history_policy_changes(tmp_path: Path) -> None:
    """short_history_exempt is metadata, not snapshot identity; same CSVs imported under
    different short-history policies must produce the same snapshot_id."""

    first_source = tmp_path / "raw-1"
    second_source = tmp_path / "raw-2"
    first_output = tmp_path / "public-cache-1"
    second_output = tmp_path / "public-cache-2"
    _write_universe_with_overrides(
        first_source,
        default_start=date(2018, 1, 1),
        default_end=date(2025, 12, 31),
        overrides={"SGOV": (date(2020, 6, 1), date(2025, 12, 31))},
    )
    _write_universe_with_overrides(
        second_source,
        default_start=date(2018, 1, 1),
        default_end=date(2025, 12, 31),
        overrides={"SGOV": (date(2020, 6, 1), date(2025, 12, 31))},
    )

    first = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=first_source,
            output_dir=first_output,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
        )
    )
    second = import_regime_adaptive_snapshot(
        RegimeAdaptiveSnapshotRequest(
            source_dir=second_source,
            output_dir=second_output,
            date_from=date(2018, 1, 1),
            date_to=date(2025, 12, 31),
            manual_confirmation=True,
            start_tolerance_business_days=10,
        )
    )

    assert first.snapshot_id == second.snapshot_id
