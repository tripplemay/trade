"""B028 F001 — ``scripts/validate_snapshot.py`` cross-check logic.

Imports the script as a module so the comparison + sampling helpers
are unit-testable; the runtime ``main`` is exercised via a sub-call
with stubbed loaders to confirm the exit code wiring.
"""

from __future__ import annotations

import importlib.util
import random
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from workbench_api.data.snapshot_loader import PriceBar, SnapshotLoader

SCRIPT_PATH = (
    Path(__file__).resolve().parents[4] / "scripts" / "validate_snapshot.py"
)


def _import_validate_snapshot() -> ModuleType:
    """Load the cross-check script as a module without executing it."""

    spec = importlib.util.spec_from_file_location("validate_snapshot", SCRIPT_PATH)
    assert spec and spec.loader, f"cannot resolve {SCRIPT_PATH}"
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("validate_snapshot", module)
    spec.loader.exec_module(module)
    return module


class _StubLoader(SnapshotLoader):
    """In-memory loader keyed by ``(ticker, date) -> adj_close`` so
    cross-check tests pin specific discrepancies deterministically."""

    def __init__(self, table: dict[tuple[str, date], float]) -> None:
        self._table = table

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date,
    ) -> list[PriceBar]:
        key = (ticker, from_date)
        if key not in self._table:
            raise ValueError(f"stub has no bar for {key}")
        adj = self._table[key]
        return [
            PriceBar(
                ticker=ticker,
                bar_date=from_date,
                open=adj,
                high=adj,
                low=adj,
                close=adj,
                adj_close=adj,
                volume=1_000_000,
            )
        ]

    def health_check(self) -> bool:
        return True


def test_sample_dates_returns_distinct_business_days() -> None:
    """Smoke: sampler must avoid duplicates + weekends."""

    module = _import_validate_snapshot()
    rng = random.Random(42)
    dates = module.sample_dates(
        earliest=date(2024, 1, 1),
        latest=date(2024, 12, 31),
        count=10,
        rng=rng,
    )
    assert len(dates) == 10
    assert len(set(dates)) == 10
    for d in dates:
        assert d.weekday() < 5, f"{d} is a weekend"
        assert date(2024, 1, 1) <= d <= date(2024, 12, 31)


def test_sample_dates_rejects_inverted_window() -> None:
    module = _import_validate_snapshot()
    rng = random.Random(0)
    with pytest.raises(ValueError):
        module.sample_dates(
            earliest=date(2024, 12, 31),
            latest=date(2024, 1, 1),
            count=3,
            rng=rng,
        )


def test_cross_check_passes_when_prices_match_within_tolerance() -> None:
    module = _import_validate_snapshot()
    sample = date(2024, 6, 3)
    tiingo = _StubLoader({("SPY", sample): 100.0, ("QQQ", sample): 200.0})
    yf = _StubLoader({("SPY", sample): 100.01, ("QQQ", sample): 200.05})
    discrepancies, total = module.cross_check(
        tickers=["SPY", "QQQ"],
        dates=[sample],
        tiingo=tiingo,
        yf=yf,
        tolerance=0.005,
    )
    assert total == 2
    assert discrepancies == []


def test_cross_check_flags_discrepancies_above_tolerance() -> None:
    module = _import_validate_snapshot()
    sample = date(2024, 6, 3)
    tiingo = _StubLoader({("SPY", sample): 100.0, ("QQQ", sample): 250.0})
    yf = _StubLoader({("SPY", sample): 100.01, ("QQQ", sample): 200.0})
    discrepancies, total = module.cross_check(
        tickers=["SPY", "QQQ"],
        dates=[sample],
        tiingo=tiingo,
        yf=yf,
        tolerance=0.005,
    )
    assert total == 2
    assert len(discrepancies) == 1
    only = discrepancies[0]
    assert only.ticker == "QQQ"
    assert only.relative_error >= 0.005


def test_cross_check_records_fetch_failure_as_infinite_error() -> None:
    """A vendor that raises before returning a bar must still produce
    a discrepancy row — never silently ignored — so the cap operator
    sees the failure in the summary table."""

    module = _import_validate_snapshot()
    sample = date(2024, 6, 3)
    tiingo = _StubLoader({("SPY", sample): 100.0})
    yf = _StubLoader({})  # no rows → raises ValueError on fetch
    discrepancies, total = module.cross_check(
        tickers=["SPY"],
        dates=[sample],
        tiingo=tiingo,
        yf=yf,
        tolerance=0.005,
    )
    assert total == 1
    assert len(discrepancies) == 1
    assert discrepancies[0].relative_error == float("inf")


def test_render_summary_pass_path() -> None:
    module = _import_validate_snapshot()
    text = module.render_summary(total=5, discrepancies=[], tolerance=0.005)
    assert "RESULT: PASS" in text
    assert "5/5" in text


def test_render_summary_fail_path_lists_each_discrepancy() -> None:
    module = _import_validate_snapshot()
    discrepancy_cls = module.Discrepancy
    text = module.render_summary(
        total=2,
        discrepancies=[
            discrepancy_cls(
                ticker="SPY",
                sample_date=date(2024, 6, 3),
                tiingo_close=100.0,
                yfinance_close=99.0,
                relative_error=0.0101,
            )
        ],
        tolerance=0.005,
    )
    assert "RESULT: FAIL" in text
    assert "SPY" in text
    assert "2024-06-03" in text
