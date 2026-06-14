"""B063 F001 — FX refresh (FRED CNY/USD + HKD/USD -> unified FX CSV).

Offline + deterministic: the FRED FX loader is faked (no key / network). Covers
the series->currency mapping (DEXCHUS->CNY / DEXHKUS->HKD), CSV schema, and
best-effort per-series failure resilience.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

from workbench_api.data.market_context_common import ObservationPoint
from workbench_api.data_refresh.fx_refresh import (
    FX_HEADER,
    FX_SERIES_CURRENCY,
    run_fx_refresh,
)


class _FakeFx:
    def __init__(
        self,
        by_series: dict[str, list[ObservationPoint]] | None = None,
        fail: set[str] | None = None,
    ) -> None:
        self._by = by_series or {}
        self._fail = fail or set()

    def fetch_fx(self, series_id: str, *, limit: int) -> list[ObservationPoint]:
        if series_id in self._fail:
            raise RuntimeError(f"boom {series_id}")
        return self._by.get(series_id, [])


def _pts(*vals: tuple[str, float]) -> list[ObservationPoint]:
    return [ObservationPoint(obs_date=date.fromisoformat(d), value=v) for d, v in vals]


def _fx_path(root: Path) -> Path:
    return root.joinpath("snapshots", "fx", "unified", "fx_daily.csv")


def test_series_currency_mapping() -> None:
    assert FX_SERIES_CURRENCY == {"DEXCHUS": "CNY", "DEXHKUS": "HKD"}


def test_fx_csv_written_with_currency_mapping(tmp_path: Path) -> None:
    fake = _FakeFx(
        {
            "DEXCHUS": _pts(("2024-01-02", 7.10), ("2024-01-03", 7.12)),
            "DEXHKUS": _pts(("2024-01-02", 7.81)),
        }
    )
    rows = run_fx_refresh(data_root=tmp_path, fx_loader=fake, limit=100)
    assert rows == 3
    with _fx_path(tmp_path).open() as handle:
        data = list(csv.reader(handle))
    assert data[0] == FX_HEADER
    cny = [r for r in data[1:] if r[1] == "CNY"]
    hkd = [r for r in data[1:] if r[1] == "HKD"]
    assert len(cny) == 2
    assert len(hkd) == 1
    assert cny[0][0] == "2024-01-02"
    assert float(cny[0][2]) == 7.10


def test_fx_fetch_failure_is_best_effort(tmp_path: Path) -> None:
    fake = _FakeFx({"DEXHKUS": _pts(("2024-01-02", 7.81))}, fail={"DEXCHUS"})
    rows = run_fx_refresh(data_root=tmp_path, fx_loader=fake)
    assert rows == 1  # DEXCHUS failed -> skipped; DEXHKUS still written
    assert _fx_path(tmp_path).exists()
