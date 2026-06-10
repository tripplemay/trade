"""B028 F001 — YFinanceSnapshotLoader behaviour.

Tests inject a stub ``ticker_factory`` so the suite never touches the
public yfinance / Yahoo Finance endpoints. The factory protocol only
requires ``history`` + ``info`` so a small stand-in class is enough.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data.yfinance_loader import YFinanceSnapshotLoader

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1].parent
    / "workbench_api"
    / "data"
    / "fixtures"
    / "yfinance_responses"
)


def _spy_dataframe() -> pd.DataFrame:
    """Load the committed yfinance shape fixture as a DataFrame."""

    raw = json.loads((FIXTURE_DIR / "spy-sample.json").read_text(encoding="utf-8"))
    df = pd.DataFrame(raw).set_index(pd.to_datetime([row["Date"] for row in raw]))
    return df.drop(columns=["Date"])


class _StubTicker:
    """Stand-in for ``yfinance.Ticker(ticker)`` instances."""

    def __init__(
        self,
        history_df: pd.DataFrame | None = None,
        info_dict: dict[str, Any] | None = None,
        history_exc: Exception | None = None,
        info_exc: Exception | None = None,
    ) -> None:
        self._history_df = history_df if history_df is not None else _spy_dataframe()
        self._info_dict = info_dict if info_dict is not None else {"shortName": "SPY ETF"}
        self._history_exc = history_exc
        self._info_exc = info_exc
        self.history_calls: list[dict[str, Any]] = []

    def history(self, **kwargs: Any) -> pd.DataFrame:
        self.history_calls.append(dict(kwargs))
        if self._history_exc is not None:
            raise self._history_exc
        return self._history_df.copy()

    @property
    def info(self) -> dict[str, Any]:
        if self._info_exc is not None:
            raise self._info_exc
        return dict(self._info_dict)


def _factory_returning(
    ticker_stub: _StubTicker,
) -> Any:
    """Return a callable that yields the same stub regardless of ticker arg."""

    def _factory(_ticker: str) -> _StubTicker:
        return ticker_stub

    return _factory


def test_fetch_daily_bars_parses_dataframe_into_price_bars() -> None:
    stub = _StubTicker()
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    bars = loader.fetch_daily_bars("SPY", date(2024, 1, 2), date(2024, 1, 4))
    assert len(bars) == 3
    first = bars[0]
    assert isinstance(first, PriceBar)
    assert first.ticker == "SPY"
    assert first.bar_date == date(2024, 1, 2)
    # adj_close must come from "Adj Close", not "Close" — auto_adjust=False
    # invariant; the bundled fixture has different values for the two so
    # the assertion catches a regression that maps the wrong column.
    assert first.close == 472.65
    assert first.adj_close == 470.12
    assert first.volume == 123_524_300


def test_fetch_daily_bars_invokes_yfinance_with_auto_adjust_false() -> None:
    """Spec invariant — without ``auto_adjust=False``, yfinance silently
    overwrites Close with the adjusted close and we lose the raw price."""

    stub = _StubTicker()
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    loader.fetch_daily_bars("SPY", date(2024, 1, 2), date(2024, 1, 4))
    assert len(stub.history_calls) == 1
    call = stub.history_calls[0]
    assert call["auto_adjust"] is False
    # end is exclusive in yfinance — loader adds +1 day so an inclusive
    # to_date still surfaces.
    assert call["end"] == "2024-01-05"


def test_fetch_daily_bars_clamps_future_to_date() -> None:
    """PIT correctness: requesting a future to_date must clamp to today
    before the yfinance call is built (the vendor returns empty for the
    future range otherwise, which raises ValueError downstream and
    obscures the user's actual intent)."""

    stub = _StubTicker()
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    # B054: the loader clamps to UTC today (B053 F003), so the test's "today"
    # must also be UTC — otherwise it diverges when local TZ is ahead of UTC.
    today = datetime.now(UTC).date()
    future = today + timedelta(days=30)
    loader.fetch_daily_bars("SPY", today - timedelta(days=7), future)
    call = stub.history_calls[0]
    # end is exclusive (+1 day from clamped to_date).
    expected_end = (today + timedelta(days=1)).isoformat()
    assert call["end"] == expected_end


def test_fetch_daily_bars_raises_on_empty_dataframe() -> None:
    stub = _StubTicker(history_df=pd.DataFrame())
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    with pytest.raises(ValueError) as exc_info:
        loader.fetch_daily_bars("BAD", date(2024, 1, 2), date(2024, 1, 4))
    assert "yfinance returned empty" in str(exc_info.value)
    assert "BAD" in str(exc_info.value)


def test_fetch_daily_bars_raises_on_missing_columns() -> None:
    """yfinance >= 0.2.30 silently drops ``Adj Close`` when
    ``auto_adjust=True``. The loader hard-pins ``auto_adjust=False``
    but if a downstream change ever flips that, the schema check
    here surfaces the missing column with the offending ticker."""

    incomplete = _spy_dataframe().drop(columns=["Adj Close"])
    stub = _StubTicker(history_df=incomplete)
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    with pytest.raises(ValueError) as exc_info:
        loader.fetch_daily_bars("SPY", date(2024, 1, 2), date(2024, 1, 4))
    message = str(exc_info.value)
    assert "Adj Close" in message
    assert "SPY" in message
    assert "auto_adjust=False" in message


def test_health_check_returns_true_when_info_is_populated() -> None:
    stub = _StubTicker(info_dict={"shortName": "SPDR S&P 500"})
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    assert loader.health_check() is True


def test_health_check_returns_false_when_info_is_empty() -> None:
    """Empty info dict — Yahoo throttling or invalid ticker — must
    surface as ``health_check() is False`` so the caller can branch
    on availability without parsing exception types."""

    stub = _StubTicker(info_dict={})
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    assert loader.health_check() is False


def test_health_check_returns_false_when_ticker_raises() -> None:
    """Yahoo intermittently returns HTTP 5xx on the .info endpoint;
    the loader must absorb the exception and return False rather than
    propagating an opaque vendor error."""

    stub = _StubTicker(info_exc=RuntimeError("Yahoo 503"))
    loader = YFinanceSnapshotLoader(ticker_factory=_factory_returning(stub))
    assert loader.health_check() is False
