"""B076 F001 — unit tests for the PIT circ-market-cap fetch helpers.

The full pull is a baostock network job; these tests lock the PURE reconstruction +
downsample logic offline (no network): the ``turn``-derived circulating-cap identity,
the skip-unusable-bar rule, the month-end downsample, and the universe union.
"""

from __future__ import annotations

import csv

import pytest

from scripts.research.b076_fetch_pit_marketcap import (
    circ_mv_from_bar,
    month_end_marketcap,
    union_tickers,
)


def test_circ_mv_matches_turn_identity() -> None:
    # 600519.SH 2024-01-02 (real): close 1685.01, vol 3_215_644, turn 0.256% → ~2.1e12.
    cap = circ_mv_from_bar("1685.0100", "3215644", "0.256000")
    assert cap is not None
    assert cap == pytest.approx(1685.01 * 3215644 * 100.0 / 0.256, rel=1e-9)
    assert 2.0e12 < cap < 2.2e12  # 贵州茅台's real circulating cap scale


def test_smaller_turn_or_price_scales_cap_correctly() -> None:
    # Halving the price halves the cap; halving turn doubles it (inverse).
    base = circ_mv_from_bar("100", "1000000", "1.0")
    assert base == pytest.approx(100 * 1_000_000 * 100.0 / 1.0)
    assert circ_mv_from_bar("50", "1000000", "1.0") == pytest.approx(base / 2)
    assert circ_mv_from_bar("100", "1000000", "0.5") == pytest.approx(base * 2)


def test_unusable_bars_return_none() -> None:
    # Suspended / no-turnover / blank bars cannot yield a cap → skipped (never 0-cap row).
    assert circ_mv_from_bar("100", "1000000", "0") is None  # turn 0 (suspended)
    assert circ_mv_from_bar("100", "0", "1.0") is None  # no volume
    assert circ_mv_from_bar("0", "1000000", "1.0") is None  # no price
    assert circ_mv_from_bar("", "", "") is None  # blank
    assert circ_mv_from_bar("100", "1000000", "-1") is None  # negative turn


def test_month_end_keeps_last_valid_per_month() -> None:
    bars = [
        ("2025-01-10", 1.0e10),
        ("2025-01-31", 1.1e10),  # last of Jan → kept
        ("2025-02-14", 2.0e10),
        ("2025-02-27", 2.2e10),  # last of Feb (literal 28th suspended) → kept
        ("2025-03-31", 3.0e10),  # only March bar → kept
    ]
    out = month_end_marketcap(bars)
    assert out == [("2025-01-31", 1.1e10), ("2025-02-27", 2.2e10), ("2025-03-31", 3.0e10)]


def test_month_end_empty() -> None:
    assert month_end_marketcap([]) == []


def test_union_tickers_dedupes_across_rebalance_blocks(tmp_path) -> None:
    path = tmp_path / "cn_pit_universe.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["as_of_date", "ticker", "rank", "market_cap", "avg_turnover", "composite_score"]
        )
        writer.writerow(["2019-03-31", "600519.SH", "1", "0.0", "0.0", "0.0"])
        writer.writerow(["2019-03-31", "000001.SZ", "2", "0.0", "0.0", "0.0"])
        writer.writerow(["2019-06-30", "600519.SH", "1", "0.0", "0.0", "0.0"])  # dup name
        writer.writerow(["2019-06-30", "000002.SZ", "2", "0.0", "0.0", "0.0"])
    assert union_tickers(path) == ["000001.SZ", "000002.SZ", "600519.SH"]
