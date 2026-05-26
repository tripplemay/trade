"""B028 F002 — ``scripts/backfill_prices.py`` + ``scripts/universe_master.py``.

Drives the backfill driver against a stub ``SnapshotLoader`` so the
suite never touches Tiingo. The full backfill on real data is a
manual one-shot (see ``data/snapshots/README.md``); these specs pin
the per-row write semantics, the sort + dedupe in the merge step,
the atomic-write guarantee, and the universe-list invariants.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType

import pytest

from workbench_api.data.snapshot_loader import PriceBar, SnapshotLoader

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"


def _import_script(name: str) -> ModuleType:
    """Load one of the repo-root ``scripts/`` modules."""

    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot resolve {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def _bar(ticker: str, day: date, close: float = 100.0) -> PriceBar:
    return PriceBar(
        ticker=ticker,
        bar_date=day,
        open=close,
        high=close,
        low=close,
        close=close,
        adj_close=close,
        volume=1_000_000,
    )


class _StubLoader(SnapshotLoader):
    """Returns bars from a pre-seeded ``ticker -> [PriceBar]`` table."""

    def __init__(self, table: dict[str, list[PriceBar]]) -> None:
        self._table = table
        self.calls: list[tuple[str, date, date]] = []

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        self.calls.append((ticker, from_date, to_date))
        if ticker not in self._table:
            raise ValueError(f"stub: no bars for {ticker}")
        return [b for b in self._table[ticker] if from_date <= b.bar_date <= to_date]

    def health_check(self) -> bool:
        return True


# --- universe_master.py invariants ----------------------------------------


def test_master_universe_size_in_spec_range() -> None:
    """Spec §F002 acceptance #3 requires 50-80 tickers in the master list."""

    universe_master = _import_script("universe_master")
    universe = universe_master.master_universe()
    assert 50 <= len(universe) <= 80, f"master universe size {len(universe)} not in [50, 80]"


def test_master_universe_contains_required_sleeve_etfs() -> None:
    """Spec §F002 acceptance #9: the 4 Master sleeve ETFs must be present."""

    universe_master = _import_script("universe_master")
    universe = set(universe_master.master_universe())
    assert {"SPY", "QQQ", "IEF", "SGOV"}.issubset(universe)


def test_master_universe_consistent_with_b025_fixture() -> None:
    """The B025 real-ticker subset must mirror
    ``data/fixtures/us_quality_momentum/universe.csv`` modulo the synthetic
    ``ZQ*`` rows, otherwise the backfill grows / shrinks out of step with
    the fixture the B030 cutover will compare against."""

    universe_master = _import_script("universe_master")
    # Helper raises AssertionError on drift; just call it.
    universe_master.assert_master_universe_consistent_with_fixture()


def test_master_universe_is_deduped() -> None:
    """Order matters (highest-value tickers first), but no duplicates."""

    universe_master = _import_script("universe_master")
    universe = universe_master.master_universe()
    assert len(universe) == len(set(universe))


# --- backfill_prices.py write semantics -----------------------------------


def test_backfill_writes_vendor_csv_with_correct_schema(tmp_path: Path) -> None:
    backfill = _import_script("backfill_prices")
    loader = _StubLoader({"SPY": [_bar("SPY", date(2024, 6, 3)), _bar("SPY", date(2024, 6, 4))]})

    row_count, failures = backfill.backfill(
        ["SPY"],
        date(2024, 6, 3),
        date(2024, 6, 4),
        loader,
        snapshots_root=tmp_path,
    )

    vendor_path = tmp_path / "prices" / "tiingo" / "SPY-2024-06-03-2024-06-04.csv"
    assert vendor_path.exists()
    with vendor_path.open() as fh:
        reader = csv.DictReader(fh)
        assert reader.fieldnames == list(backfill.UNIFIED_COLUMNS)
        rows = list(reader)
    assert len(rows) == 2
    assert rows[0]["ticker"] == "SPY"
    assert rows[0]["date"] == "2024-06-03"
    assert failures == []
    assert row_count == 2


def test_backfill_appends_into_unified_sorted_and_deduped(tmp_path: Path) -> None:
    backfill = _import_script("backfill_prices")
    # Seed unified with an existing day so we can prove the merge respects it.
    unified_path = tmp_path / "prices" / "unified" / "prices_daily.csv"
    unified_path.parent.mkdir(parents=True, exist_ok=True)
    with unified_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=backfill.UNIFIED_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "date": "2024-06-02",
                "ticker": "AAPL",
                "open": "190.0",
                "high": "190.0",
                "low": "190.0",
                "close": "190.0",
                "adj_close": "190.0",
                "volume": "1000000",
            }
        )

    loader = _StubLoader(
        {
            "SPY": [_bar("SPY", date(2024, 6, 3), 540.0)],
            "QQQ": [_bar("QQQ", date(2024, 6, 3), 480.0)],
            # AAPL re-fetch must update (dedupe by (ticker, date)).
            "AAPL": [_bar("AAPL", date(2024, 6, 2), 191.0)],
        }
    )
    row_count, failures = backfill.backfill(
        ["SPY", "QQQ", "AAPL"],
        date(2024, 6, 2),
        date(2024, 6, 3),
        loader,
        snapshots_root=tmp_path,
    )
    assert failures == []
    # 1 AAPL (deduped) + 1 SPY + 1 QQQ = 3 rows, sorted by (ticker, date).
    with unified_path.open() as fh:
        rows = list(csv.DictReader(fh))
    assert row_count == 3
    assert [(r["ticker"], r["date"]) for r in rows] == [
        ("AAPL", "2024-06-02"),
        ("QQQ", "2024-06-03"),
        ("SPY", "2024-06-03"),
    ]
    # Dedup updated the AAPL close — the new value won.
    assert float(rows[0]["close"]) == 191.0


def test_validate_bars_rejects_negative_ohlc() -> None:
    backfill = _import_script("backfill_prices")
    bad = PriceBar(
        ticker="SPY",
        bar_date=date(2024, 6, 3),
        open=540.0,
        high=540.0,
        low=-1.0,  # negative — invalid
        close=540.0,
        adj_close=540.0,
        volume=1_000_000,
    )
    with pytest.raises(ValueError) as exc_info:
        backfill.validate_bars("SPY", [bad])
    assert "negative" in str(exc_info.value).lower()


def test_validate_bars_rejects_ticker_mismatch() -> None:
    backfill = _import_script("backfill_prices")
    mismatch = PriceBar(
        ticker="QQQ",
        bar_date=date(2024, 6, 3),
        open=540.0,
        high=540.0,
        low=540.0,
        close=540.0,
        adj_close=540.0,
        volume=1_000_000,
    )
    with pytest.raises(ValueError) as exc_info:
        backfill.validate_bars("SPY", [mismatch])
    assert "mismatch" in str(exc_info.value).lower()


def test_validate_bars_rejects_empty_bar_list() -> None:
    backfill = _import_script("backfill_prices")
    with pytest.raises(ValueError) as exc_info:
        backfill.validate_bars("SPY", [])
    assert "empty" in str(exc_info.value).lower()


def test_atomic_write_leaves_old_unified_when_a_fetch_fails(tmp_path: Path) -> None:
    """The merge step must not rewrite ``prices_daily.csv`` if any
    ticker fetch raised. The vendor partial files stay on disk for
    diagnosis; the unified row count returned is the pre-existing
    value (or zero if no unified file existed)."""

    backfill = _import_script("backfill_prices")
    # Seed unified with a known-good day.
    unified_path = tmp_path / "prices" / "unified" / "prices_daily.csv"
    unified_path.parent.mkdir(parents=True, exist_ok=True)
    with unified_path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=backfill.UNIFIED_COLUMNS)
        writer.writeheader()
        writer.writerow(
            {
                "date": "2024-06-02",
                "ticker": "SPY",
                "open": "1.0",
                "high": "1.0",
                "low": "1.0",
                "close": "1.0",
                "adj_close": "1.0",
                "volume": "1",
            }
        )
    seed_text = unified_path.read_text()

    loader = _StubLoader({"SPY": [_bar("SPY", date(2024, 6, 3), 540.0)]})  # no QQQ
    row_count, failures = backfill.backfill(
        ["SPY", "QQQ"],
        date(2024, 6, 3),
        date(2024, 6, 3),
        loader,
        snapshots_root=tmp_path,
    )
    assert failures, "expected QQQ fetch to fail"
    # Unified untouched.
    assert unified_path.read_text() == seed_text
    # Vendor file for SPY exists despite the partial run.
    assert (tmp_path / "prices" / "tiingo" / "SPY-2024-06-03-2024-06-03.csv").exists()
    # row_count reflects the pre-existing file (1 row).
    assert row_count == 1


def test_main_argparse_defaults_to_master_universe(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No ``--tickers`` + no explicit ``--universe`` should walk the
    full master list. We hijack the TiingoSnapshotLoader constructor
    so the subprocess never reaches the network."""

    backfill = _import_script("backfill_prices")
    universe_master = _import_script("universe_master")

    seen: dict[str, list[tuple[str, date, date]]] = {"calls": []}

    class _CapturingLoader(SnapshotLoader):
        def fetch_daily_bars(
            self, ticker: str, from_date: date, to_date: date
        ) -> list[PriceBar]:
            seen["calls"].append((ticker, from_date, to_date))
            return [_bar(ticker, from_date, 100.0)]

        def health_check(self) -> bool:
            return True

    monkeypatch.setattr(backfill, "TiingoSnapshotLoader", lambda: _CapturingLoader())
    exit_code = backfill.main(
        [
            "--from",
            "2024-06-03",
            "--to",
            "2024-06-03",
            "--snapshots-root",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    fetched_tickers = [call[0] for call in seen["calls"]]
    assert fetched_tickers == universe_master.master_universe()


def test_gitignore_excludes_csv_keeps_readme() -> None:
    """Spec §F002 acceptance #8 — vendor CSV stays out of git; the
    layout README stays in."""

    gitignore = REPO_ROOT / "data" / "snapshots" / ".gitignore"
    text = gitignore.read_text(encoding="utf-8")
    assert "*.csv" in text
    assert "!README.md" in text
