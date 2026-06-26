"""B078 F001 — per-call fetch timeout (杜绝挂死) for the A-share refresh loop.

Two layers, both deterministic (no network):

* :func:`call_with_timeout` primitive — returns within the deadline, raises
  :class:`FetchTimeoutError` on overrun (at the deadline, NOT at the block's end),
  propagates the wrapped exception, and runs inline when disabled (0 / None).
* ``run_refresh`` integration — a CN loader that HANGS on one wide-universe symbol
  is bounded by the per-call timeout: the hung symbol is counted as a §34
  partial-failure, the survivor is still written, and the refresh COMPLETES
  instead of wedging (the 2026-06-22 3-day stuck-``activating`` root cause).
"""

from __future__ import annotations

import threading
import time
from datetime import date
from pathlib import Path

import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data_refresh.call_timeout import FetchTimeoutError, call_with_timeout
from workbench_api.data_refresh.refresh import run_refresh

_FROM = date(2023, 1, 1)
_TO = date(2024, 12, 31)
# Block far longer than any deadline so a leaked worker proves the TIMEOUT fired
# (not the loader returning on its own); it is bounded so it self-terminates and
# never wedges the test runner.
_BLOCK_SECONDS = 30.0


def _bar(ticker: str) -> PriceBar:
    return PriceBar(
        ticker=ticker,
        bar_date=date(2024, 12, 31),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        adj_close=100.5,
        volume=1000,
    )


# --------------------------------------------------------------------------- #
# call_with_timeout primitive
# --------------------------------------------------------------------------- #


def test_returns_value_within_deadline() -> None:
    assert call_with_timeout(5.0, lambda: 42) == 42


def test_passes_through_args_and_kwargs() -> None:
    assert call_with_timeout(5.0, lambda a, b: a + b, 2, b=3) == 5


def test_propagates_wrapped_exception() -> None:
    def boom() -> int:
        raise ValueError("kaboom")

    with pytest.raises(ValueError, match="kaboom"):
        call_with_timeout(5.0, boom)


def test_raises_fetch_timeout_on_overrun() -> None:
    def slow() -> int:
        threading.Event().wait(_BLOCK_SECONDS)
        return 1

    with pytest.raises(FetchTimeoutError):
        call_with_timeout(0.05, slow)


def test_overrun_returns_at_deadline_not_block_end() -> None:
    def slow() -> None:
        threading.Event().wait(_BLOCK_SECONDS)

    t0 = time.monotonic()
    with pytest.raises(FetchTimeoutError):
        call_with_timeout(0.1, slow)
    # Returned ~at the 0.1s deadline, not after the 30s block → the bound worked.
    assert time.monotonic() - t0 < 5.0


def test_disabled_timeout_runs_inline() -> None:
    # 0 / None disables the bound: runs inline (no worker thread), returns the
    # value directly, and still propagates exceptions — byte-identical to a
    # direct call, the pre-B078 behaviour every existing caller relies on.
    assert call_with_timeout(0, lambda: 7) == 7
    assert call_with_timeout(-1.0, lambda: 7) == 7

    def boom() -> int:
        raise KeyError("nope")

    with pytest.raises(KeyError):
        call_with_timeout(0, boom)


# --------------------------------------------------------------------------- #
# run_refresh integration — a hung wide-universe symbol cannot wedge the loop
# --------------------------------------------------------------------------- #


class _HangingCnLoader:
    """CN/HK loader that BLOCKS on ``hang`` symbols (simulating a network hang)
    and returns one bar for everything else. The block is bounded so a leaked
    worker thread self-terminates — it must never wedge the test runner."""

    def __init__(self, hang: set[str], *, block_seconds: float = _BLOCK_SECONDS) -> None:
        self.hang = hang
        self.block_seconds = block_seconds
        self.calls: list[str] = []

    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        self.calls.append(ticker)
        if ticker in self.hang:
            threading.Event().wait(self.block_seconds)
            raise RuntimeError("released after block")  # unreached within deadline
        return [_bar(ticker)]


class _FakeFundamentals:
    @property
    def ticker_cik_map(self) -> dict[str, int | None]:
        return {}

    def fetch_raw_companyfacts(self, ticker: str) -> dict[str, object]:  # pragma: no cover
        raise AssertionError("not used")


class _FakePrices:
    def fetch_daily_bars(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[PriceBar]:
        return [_bar(ticker)]


def test_hung_wide_symbol_times_out_counted_partial_failure_and_completes(
    tmp_path: Path,
) -> None:
    loader = _HangingCnLoader(hang={"600999.SH"})

    t0 = time.monotonic()
    summary = run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_hk_prices_loader=loader,
        # Two wide-universe extension symbols: one hangs, one survives.
        cn_extra_price_symbols=["600999.SH", "000001.SZ"],
        cn_fetch_timeout_seconds=0.2,
    )
    elapsed = time.monotonic() - t0

    # The refresh COMPLETED quickly — the hang was bounded, not waited out.
    assert elapsed < 10.0
    # The loop ADVANCED past the hung symbol to the survivor.
    assert "000001.SZ" in loader.calls
    # The hung symbol is isolated to the wide-block error tally (§34 partial-failure).
    assert summary.cn_universe_price_symbols == 2
    assert summary.cn_universe_price_errors == 1
    assert summary.errors >= 1
    # The survivor's row is still written (不炸整轮).
    rows = (tmp_path / "snapshots" / "prices" / "unified" / "prices_daily.csv").read_text(
        encoding="utf-8"
    )
    assert "000001.SZ" in rows
    assert "600999.SH" not in rows


def test_disabled_timeout_is_backward_compatible(tmp_path: Path) -> None:
    # cn_fetch_timeout_seconds=None (the default) runs every fetch inline — the
    # fast fake loader behaves exactly as pre-B078 (no symbol hangs here).
    loader = _HangingCnLoader(hang=set())
    summary = run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_hk_prices_loader=loader,
        cn_extra_price_symbols=["000001.SZ"],
    )
    assert summary.cn_universe_price_errors == 0
    assert summary.cn_universe_price_symbols == 1


# --------------------------------------------------------------------------- #
# Bulk-discovery + benchmark fetches — the last unbounded A-share network calls
# (review finding: discovery runs BEFORE run_refresh on the daily critical path)
# --------------------------------------------------------------------------- #


class _HangingAkshare:
    """Fake akshare whose bulk spot endpoints HANG (bounded so they self-release)."""

    def __init__(self, block_seconds: float = _BLOCK_SECONDS) -> None:
        self.block_seconds = block_seconds

    def stock_zh_a_spot_em(self) -> object:
        threading.Event().wait(self.block_seconds)
        raise RuntimeError("released after block")

    def stock_zh_a_spot(self) -> object:
        threading.Event().wait(self.block_seconds)
        raise RuntimeError("released after block")


def test_hung_bulk_discovery_times_out_and_degrades_to_seed() -> None:
    from workbench_api.data_refresh.cn_marketcap import discover_ashare_superset
    from workbench_api.data_refresh.cn_universe import CN_UNIVERSE_SEED

    t0 = time.monotonic()
    # allow_sina_fallback=True → BOTH bulk sources are tried; each must time out
    # (per-source bound) and discovery degrades to the curated seed, not hang.
    symbols, provenance = discover_ashare_superset(
        _HangingAkshare(),
        top_n=50,
        allow_sina_fallback=True,
        fetch_timeout_seconds=0.2,
    )
    elapsed = time.monotonic() - t0
    assert elapsed < 10.0  # two 0.2s timeouts, not two 30s blocks
    assert provenance == "seed"
    assert symbols == CN_UNIVERSE_SEED


class _HangingCsiLoader:
    def fetch_index_close(self, symbol: str) -> list[tuple[date, float]]:
        threading.Event().wait(_BLOCK_SECONDS)
        return []


def test_hung_benchmark_fetch_times_out_returns_zero(tmp_path: Path) -> None:
    from workbench_api.data_refresh.cn_benchmark import run_cn_benchmark_refresh

    t0 = time.monotonic()
    rows = run_cn_benchmark_refresh(
        data_root=tmp_path,
        loader=_HangingCsiLoader(),
        fetch_timeout_seconds=0.2,
    )
    assert time.monotonic() - t0 < 5.0
    assert rows == 0  # best-effort: a hang degrades to "benchmark unavailable"
