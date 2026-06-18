"""B066 F001 — unit tests for the CN point-in-time universe loader."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from trade.data.cn_attack_universe import (
    CnUniverseError,
    load_cn_universe,
    load_cn_universe_members,
)

_HEADER = "as_of_date,ticker,rank,market_cap,avg_turnover,composite_score\n"


def _write_universe(path: Path, rows: list[tuple[str, str, int]]) -> None:
    lines = [_HEADER]
    for as_of_date, ticker, rank in rows:
        # market_cap / avg_turnover / composite_score are not asserted here; the
        # PIT-membership contract is about which (date, ticker) block is returned.
        lines.append(f"{as_of_date},{ticker},{rank},1.0e12,1.0e9,0.5\n")
    path.write_text("".join(lines), encoding="utf-8")


@pytest.fixture
def universe_csv(tmp_path: Path) -> Path:
    path = tmp_path / "cn_pit_universe.csv"
    _write_universe(
        path,
        [
            ("2024-03-31", "600519.SH", 1),
            ("2024-03-31", "000858.SZ", 2),
            ("2024-03-31", "600036.SH", 3),
            ("2024-06-30", "600519.SH", 1),
            ("2024-06-30", "000858.SZ", 2),
            ("2024-06-30", "300750.SZ", 3),  # 600036 dropped, 300750 added
        ],
    )
    return path


def test_returns_latest_block_on_or_before_as_of(universe_csv: Path) -> None:
    # as_of between the two rebalances → the EARLIER (2024-03-31) block, never the
    # not-yet-known 2024-06-30 one (point-in-time, no look-ahead).
    members = load_cn_universe(date(2024, 5, 15), universe_path=universe_csv)
    assert members == ("600519.SH", "000858.SZ", "600036.SH")


def test_does_not_leak_future_rebalance(universe_csv: Path) -> None:
    # The 2024-06-30 block (which adds 300750.SZ) must be invisible on 2024-05-15.
    members = load_cn_universe(date(2024, 5, 15), universe_path=universe_csv)
    assert "300750.SZ" not in members


def test_uses_block_when_as_of_equals_rebalance(universe_csv: Path) -> None:
    members = load_cn_universe(date(2024, 6, 30), universe_path=universe_csv)
    assert members == ("600519.SH", "000858.SZ", "300750.SZ")


def test_empty_before_first_rebalance(universe_csv: Path) -> None:
    assert load_cn_universe(date(2024, 1, 1), universe_path=universe_csv) == ()


def test_members_ordered_by_rank(universe_csv: Path) -> None:
    members = load_cn_universe_members(date(2024, 3, 31), universe_path=universe_csv)
    assert [m.rank for m in members] == [1, 2, 3]
    assert all(m.as_of == date(2024, 3, 31) for m in members)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(CnUniverseError, match="missing"):
        load_cn_universe(date(2024, 5, 15), universe_path=tmp_path / "nope.csv")


def test_missing_column_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text("as_of_date,ticker,rank\n2024-03-31,600519.SH,1\n", encoding="utf-8")
    with pytest.raises(CnUniverseError, match="missing required columns"):
        load_cn_universe(date(2024, 5, 15), universe_path=path)


def test_bad_date_raises(tmp_path: Path) -> None:
    path = tmp_path / "bad_date.csv"
    path.write_text(_HEADER + "31-03-2024,600519.SH,1,1e12,1e9,0.5\n", encoding="utf-8")
    with pytest.raises(CnUniverseError, match="YYYY-MM-DD"):
        load_cn_universe(date(2024, 5, 15), universe_path=path)
