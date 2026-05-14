import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from trade.strategies.regime_adaptive.snapshot import (
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
