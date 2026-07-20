"""B076 F001 — unit tests for the PIT circ-market-cap fetch helpers.

The full pull is a baostock network job; these tests lock the PURE reconstruction +
downsample logic offline (no network): the ``turn``-derived circulating-cap identity,
the skip-unusable-bar rule, the month-end downsample, and the universe union.

★★B109 F002 起 :func:`circ_mv_from_bar` **已弃用**（返回流通市值，违上游禁令 #6）。

B109 F003 验收指出：这些断言原本只验算术正确，等于给一条被禁的路径**盖绿色印章**——
未来 agent 检索 "market cap" 会同时命中新旧两条，且旧的看起来测试齐全。
现在每个调用点都**必须**断言 ``DeprecationWarning``，禁令因此被测试固化而非仅写在注释里。
"""

from __future__ import annotations

import csv

import pytest

from scripts.research.b076_fetch_pit_marketcap import (
    circ_mv_from_bar,
    month_end_marketcap,
    union_tickers,
)


def _deprecated_cap(close: str, volume: str, turn: str) -> float | None:
    """调用弃用函数并**强制**断言它确实告警。漏告警即测试失败。"""
    with pytest.warns(DeprecationWarning, match="禁令 #6"):
        return circ_mv_from_bar(close, volume, turn)


def test_circ_mv_from_bar_is_deprecated_and_says_why() -> None:
    """★禁令 #6 由测试固化：告警必须指明替代品，否则读者不知道该改用什么。"""
    with pytest.warns(DeprecationWarning) as record:
        circ_mv_from_bar("100", "1000000", "1.0")
    message = str(record[0].message)
    assert "禁令 #6" in message
    assert "流通市值" in message
    assert "ashare_pit/marketcap.py" in message


def test_circ_mv_matches_turn_identity() -> None:
    # 600519.SH 2024-01-02 (real): close 1685.01, vol 3_215_644, turn 0.256% → ~2.1e12.
    # ★算术正确 ≠ 口径正确：这是**流通**市值，全公司归母利润的分母须用**总**市值。
    cap = _deprecated_cap("1685.0100", "3215644", "0.256000")
    assert cap is not None
    assert cap == pytest.approx(1685.01 * 3215644 * 100.0 / 0.256, rel=1e-9)
    assert 2.0e12 < cap < 2.2e12  # 贵州茅台's real circulating cap scale


def test_smaller_turn_or_price_scales_cap_correctly() -> None:
    # Halving the price halves the cap; halving turn doubles it (inverse).
    base = _deprecated_cap("100", "1000000", "1.0")
    assert base == pytest.approx(100 * 1_000_000 * 100.0 / 1.0)
    assert _deprecated_cap("50", "1000000", "1.0") == pytest.approx(base / 2)
    assert _deprecated_cap("100", "1000000", "0.5") == pytest.approx(base * 2)


def test_unusable_bars_return_none() -> None:
    # Suspended / no-turnover / blank bars cannot yield a cap → skipped (never 0-cap row).
    assert _deprecated_cap("100", "1000000", "0") is None  # turn 0 (suspended)
    assert _deprecated_cap("100", "0", "1.0") is None  # no volume
    assert _deprecated_cap("0", "1000000", "1.0") is None  # no price
    assert _deprecated_cap("", "", "") is None  # blank
    assert _deprecated_cap("100", "1000000", "-1") is None  # negative turn


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
