"""yfinance SnapshotLoader — free cross-check companion to Tiingo.

Per ``docs/product/data-source-evaluation-2026-05.md`` §6.1, yfinance
is a non-official wrapper around Yahoo Finance. We use it **only for
cross-check** — the production ingest path runs through Tiingo via
:class:`workbench_api.data.tiingo_loader.TiingoSnapshotLoader`. The
cross-check script (``scripts/validate_snapshot.py``) compares prices
on a small random sample and reports any > 0.5 % discrepancy.

Two implementation notes:

* No cost guard wiring. yfinance has no monthly cap or paid tier, so
  the ``MonthlyBudgetGuard`` machinery does not apply. The class
  still inherits :class:`SnapshotLoader` so the abstract contract
  stays uniform for callers that don't care which vendor they're
  hitting.
* ``yfinance.Ticker`` is the only third-party entry point. We
  encapsulate it behind a ``ticker_factory`` callable so unit tests
  can inject a stub class without monkey-patching the ``yfinance``
  module. Production callers use the default.

``auto_adjust=False`` is non-negotiable: with the default
``auto_adjust=True`` in recent yfinance versions, the ``Close`` column
silently becomes the split/dividend-adjusted close and the raw
``Close`` is dropped. We need both ``close`` (raw) and ``adj_close``
(adjusted) to match :class:`PriceBar`'s schema 1:1 with Tiingo.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any, Protocol

import yfinance  # type: ignore[import-untyped]

from workbench_api.data.snapshot_loader import PriceBar, SnapshotLoader


class _Ticker(Protocol):
    """Subset of ``yfinance.Ticker`` the loader actually uses."""

    def history(self, **kwargs: Any) -> Any: ...

    @property
    def info(self) -> dict[str, Any]: ...


class _TickerFactory(Protocol):
    def __call__(self, ticker: str) -> _Ticker: ...


class YFinanceSnapshotLoader(SnapshotLoader):
    """SnapshotLoader implementation backed by yfinance.

    Not the production ingest path; intended for cross-check only.
    """

    def __init__(self, ticker_factory: _TickerFactory | None = None) -> None:
        self._ticker_factory: _TickerFactory = ticker_factory or yfinance.Ticker

    def fetch_daily_bars(
        self,
        ticker: str,
        from_date: date,
        to_date: date,
    ) -> list[PriceBar]:
        clamped_to = min(to_date, datetime.now(UTC).date())
        ticker_obj = self._ticker_factory(ticker)
        # yfinance.history end is exclusive — add 1 day so the
        # caller's inclusive [from_date, to_date] semantics survive.
        df = ticker_obj.history(
            start=from_date.isoformat(),
            end=(clamped_to + timedelta(days=1)).isoformat(),
            auto_adjust=False,
            actions=False,
        )
        if df is None or df.empty:
            raise ValueError(
                f"yfinance returned empty data for {ticker} "
                f"{from_date.isoformat()}..{clamped_to.isoformat()}; "
                "Yahoo may have rate-limited or the ticker may be delisted"
            )
        required_columns = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}
        missing = required_columns - set(df.columns)
        if missing:
            raise ValueError(
                f"yfinance returned DataFrame for {ticker} missing columns "
                f"{sorted(missing)}; auto_adjust=False contract violated. "
                f"Got columns: {sorted(df.columns)}"
            )
        bars: list[PriceBar] = []
        for idx, row in df.iterrows():
            # yfinance index is a pandas Timestamp; convert to date.
            bar_date = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
            bars.append(
                PriceBar(
                    ticker=ticker,
                    bar_date=bar_date,
                    open=float(row["Open"]),
                    high=float(row["High"]),
                    low=float(row["Low"]),
                    close=float(row["Close"]),
                    adj_close=float(row["Adj Close"]),
                    volume=int(row["Volume"]),
                )
            )
        return bars

    def health_check(self) -> bool:
        try:
            info = self._ticker_factory("SPY").info
        except Exception:
            return False
        return bool(info)
