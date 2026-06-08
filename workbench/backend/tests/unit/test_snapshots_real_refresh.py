"""B049 F001 — Snapshots refresh reads the real on-disk data state.

Milestone-C close-out regression: the F011 refresh streamed a *synthetic*
5-stage animation (fixed ``0.05s`` sleeps) and persisted a constant
``quality_status="ok"`` placeholder row. These tests pin the replacement:

1. ``inventory`` reads real row/symbol/window coverage from the unified CSVs.
2. ``grade_quality`` grades from real coverage, never a constant placeholder.
3. The refresh streams stages that reflect the real read (real symbol/row
   counts in the details) — not the old ``prepare/fetch/process/store`` synthetic
   sequence — and the SnapshotMeta row records the real ``manifest_path`` +
   graded ``quality_status``.
4. The error path still yields a ``stage: error`` event and re-raises.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.data_refresh import inventory
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.snapshot import SnapshotMetaRepository
from workbench_api.services import snapshots as snapshots_service

PRICES_HEADER = "date,ticker,open,high,low,close,adj_close,volume\n"
FUNDAMENTALS_HEADER = (
    "report_date,ticker,fiscal_quarter,fiscal_quarter_end,roe,gross_margin,"
    "fcf_yield,debt_to_assets,pe,pb,ev_ebitda,earnings_yield\n"
)


def _write_prices(root: Path) -> Path:
    path = root.joinpath(*inventory.PRICES_RELPATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        PRICES_HEADER
        + "2021-06-09,SPY,1,1,1,1,1,100\n"
        + "2021-06-09,AGG,1,1,1,1,1,100\n"
        + "2026-06-05,SPY,2,2,2,2,2,200\n",
        encoding="utf-8",
    )
    return path


def _write_fundamentals(root: Path) -> Path:
    path = root.joinpath(*inventory.FUNDAMENTALS_RELPATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        FUNDAMENTALS_HEADER + "2025-12-31,AAPL,Q4,2025-12-31,0.1,0.4,0.05,0.2,30,40,20,0.04\n",
        encoding="utf-8",
    )
    return path


# --- inventory (pure CSV read) -------------------------------------------------


def test_read_inventory_counts_symbols_rows_and_window(tmp_path: Path) -> None:
    prices_path = _write_prices(tmp_path)
    inv = inventory.read_inventory(prices_path)
    assert inv.present is True
    assert inv.rows == 3
    assert inv.symbols == 2  # SPY + AGG
    assert inv.data_start is not None and inv.data_start.isoformat() == "2021-06-09"
    assert inv.data_end is not None and inv.data_end.isoformat() == "2026-06-05"


def test_read_inventory_absent_file_is_empty(tmp_path: Path) -> None:
    inv = inventory.read_inventory(tmp_path / "missing.csv")
    assert inv.present is False
    assert inv.rows == 0 and inv.symbols == 0


def test_grade_quality_grades_from_real_coverage(tmp_path: Path) -> None:
    prices = inventory.read_inventory(_write_prices(tmp_path))
    fundamentals = inventory.read_inventory(_write_fundamentals(tmp_path))
    assert inventory.grade_quality(prices, fundamentals) == "ok"

    empty = inventory.read_inventory(tmp_path / "missing.csv")
    assert inventory.grade_quality(empty, fundamentals) == "degraded:no-prices"
    assert inventory.grade_quality(prices, empty) == "degraded:no-fundamentals"


# --- refresh stream (real progress + real SnapshotMeta) ------------------------


def _collect_events(factory: sessionmaker[Session]) -> list[dict[str, object]]:
    async def _run() -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        async for chunk in snapshots_service.refresh_event_stream(factory):
            line = chunk.strip()
            assert line.startswith("data: ")
            events.append(json.loads(line[len("data: ") :]))
        return events

    return asyncio.run(_run())


@pytest.fixture
def factory(initialised_db: str) -> Iterator[sessionmaker[Session]]:
    yield sessionmaker(bind=get_engine(), autoflush=False, future=True)


def test_refresh_streams_real_stages_and_records_real_meta(
    factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))
    prices_path = _write_prices(tmp_path)
    _write_fundamentals(tmp_path)

    events = _collect_events(factory)
    stages = [event["stage"] for event in events]

    # Real read stages — NOT the old synthetic prepare/fetch/process/store set.
    assert stages == ["locate", "read_prices", "read_fundamentals", "grade", "complete"]
    assert "prepare" not in stages and "process" not in stages and "store" not in stages
    assert "error" not in stages

    by_stage = {event["stage"]: event for event in events}
    # The detail reflects the real inventory counts (2 symbols, 3 rows).
    assert "2 symbols" in str(by_stage["read_prices"]["detail"])
    assert "3 rows" in str(by_stage["read_prices"]["detail"])
    assert "ok" in str(by_stage["grade"]["detail"])

    # SnapshotMeta row records the real manifest path + graded quality (no placeholder).
    with Session(get_engine()) as session:
        rows = SnapshotMetaRepository(session).list_all()
    assert len(rows) == 1
    row = rows[0]
    assert row.manifest_path == str(prices_path)
    assert row.quality_status == "ok"


def test_refresh_degraded_quality_when_data_missing(
    factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Empty data root → no prices CSV → degraded quality (not a constant "ok").
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))
    events = _collect_events(factory)
    by_stage = {event["stage"]: event for event in events}
    assert "complete" in by_stage
    with Session(get_engine()) as session:
        row = SnapshotMetaRepository(session).list_all()[0]
    assert row.quality_status == "degraded:no-prices"


def test_refresh_error_path_yields_error_event_and_reraises(
    factory: sessionmaker[Session],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))

    def _boom(_root: Path) -> inventory.CsvInventory:
        raise RuntimeError("disk exploded")

    monkeypatch.setattr(snapshots_service.inventory, "prices_inventory", _boom)

    async def _run() -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        with pytest.raises(RuntimeError, match="disk exploded"):
            async for chunk in snapshots_service.refresh_event_stream(factory):
                events.append(json.loads(chunk.strip()[len("data: ") :]))
        return events

    events = asyncio.run(_run())
    stages = [event["stage"] for event in events]
    assert "error" in stages
    assert "complete" not in stages
