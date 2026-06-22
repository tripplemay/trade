"""B073 F001 — akshare / yfinance frame-fixture replay (offline, non-HTTP).

The akshare (A-share) and yfinance loaders are *not* httpx clients — they call a
lazily-imported data library that returns a pandas-like frame. So instead of a
VCR HTTP cassette, the recorded artifact is a committed CSV "frame fixture"
(``tests/fixtures/frames/``) replayed through each loader's existing injection
seam (``akshare_module=`` / ``ticker_factory=``). This gives the same property
the HTTP cassettes give: a deterministic, offline, committed snapshot of the
external data shape that catches a parse regression and can be re-recorded when
the upstream frame schema drifts.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data.yfinance_loader import YFinanceSnapshotLoader
from workbench_api.symbols.cn_provider import CnSymbolProvider

FRAME_FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "frames"


# --- akshare (A-share) frame fixture --------------------------------------- #


class _CsvFrame:
    """Minimal stand-in for the akshare DataFrame surface (``.columns`` +
    ``.to_dict('records')``) backed by a committed CSV frame fixture."""

    def __init__(self, columns: list[str], records: list[dict[str, Any]]) -> None:
        self.columns = columns
        self._records = records

    def to_dict(self, orient: str) -> list[dict[str, Any]]:
        assert orient == "records"
        return list(self._records)


class _CsvAkshare:
    """akshare module stand-in whose ``stock_zh_a_hist`` replays a CSV frame."""

    def __init__(self, frame: _CsvFrame) -> None:
        self._frame = frame

    def stock_zh_a_hist(
        self, *, symbol: str, period: str, start_date: str, end_date: str, adjust: str
    ) -> _CsvFrame:
        return self._frame


def _load_csv_frame(name: str) -> _CsvFrame:
    rows = list(csv.DictReader((FRAME_FIXTURE_DIR / name).read_text(encoding="utf-8").splitlines()))
    columns = list(rows[0].keys()) if rows else []
    return _CsvFrame(columns=columns, records=rows)


def test_akshare_frame_fixture_replays_offline() -> None:
    """Committed Chinese-headed CSV frame → deterministic A-share PriceBars."""

    fake = _CsvAkshare(_load_csv_frame("akshare_600519_daily.csv"))
    provider = CnSymbolProvider(akshare_module=fake)

    bars = provider.get_price_history("600519.SH", date(2026, 5, 20), date(2026, 5, 22))

    assert provider.last_source == "akshare"
    assert [b.bar_date for b in bars] == [date(2026, 5, 20), date(2026, 5, 21), date(2026, 5, 22)]
    first = bars[0]
    assert isinstance(first, PriceBar)
    assert "600519" in first.ticker
    assert first.close == 1692.30
    # qfq convention: the adjusted close IS the close (no separate field).
    assert first.adj_close == 1692.30
    assert first.volume == 32100


# --- yfinance frame fixture ------------------------------------------------ #


class _StubTicker:
    """Stand-in for ``yfinance.Ticker(...)`` replaying a CSV frame fixture."""

    def __init__(self, history_df: pd.DataFrame) -> None:
        self._history_df = history_df

    def history(self, **_kwargs: Any) -> pd.DataFrame:
        return self._history_df.copy()

    @property
    def info(self) -> dict[str, Any]:
        return {"shortName": "SPY ETF"}


def _load_yfinance_frame(name: str) -> pd.DataFrame:
    raw = pd.read_csv(FRAME_FIXTURE_DIR / name)
    return raw.set_index(pd.to_datetime(raw["Date"])).drop(columns=["Date"])


def test_yfinance_frame_fixture_replays_offline() -> None:
    """Committed OHLCV CSV frame → deterministic PriceBars, Adj Close preserved."""

    stub = _StubTicker(_load_yfinance_frame("yfinance_spy_daily.csv"))
    loader = YFinanceSnapshotLoader(ticker_factory=lambda _ticker: stub)

    bars = loader.fetch_daily_bars("SPY", date(2026, 5, 20), date(2026, 5, 22))

    assert [b.bar_date for b in bars] == [date(2026, 5, 20), date(2026, 5, 21), date(2026, 5, 22)]
    first = bars[0]
    assert first.ticker == "SPY"
    # close vs adj_close differ in the fixture: a regression mapping the wrong
    # column (auto_adjust=False invariant) would be caught here.
    assert first.close == 522.65
    assert first.adj_close == 520.12
    assert first.volume == 71_240_000
