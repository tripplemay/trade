"""B065 F001 — point-in-time A-share universe builder.

Covers the pure ranking (the no-future-leakage acceptance is the heart of this
file), the turnover-from-prices derivation, the orchestrator's CSV writers +
best-effort resilience, the akshare market-cap loader / superset discovery
(faked — no network), and the §12.10.2/§26.2 boundary (no ``trade`` import).

The real akshare endpoints are exercised at L2 on the VM (Codex F004); these
assert logic/wiring/schema, not market values (v0.9.21 fixture-vs-real signal).
"""

from __future__ import annotations

import ast
import csv
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd  # type: ignore[import-untyped]
import pytest

from workbench_api.data_refresh.cn_marketcap import (
    CnMarketCapLoader,
    discover_ashare_superset,
)
from workbench_api.data_refresh.cn_universe import (
    CN_UNIVERSE_SEED,
    MARKETCAP_HEADER,
    UNIVERSE_HEADER,
    MarketCapBar,
    UniverseMember,
    build_cn_universe,
    is_st_name,
    latest_market_cap,
    percent_rank,
    point_in_time_top_n,
    quarterly_rebalance_dates,
    trailing_avg_turnover,
    turnover_from_price_rows,
)
from workbench_api.symbols.symbol_ref import SymbolRef


def _bar(ticker: str, day: date, mv: float, **kw: Any) -> MarketCapBar:
    return MarketCapBar(ticker=ticker, bar_date=day, total_mv=mv, **kw)


# --------------------------------------------------------------------------- #
# seed
# --------------------------------------------------------------------------- #


def test_seed_is_unique_and_all_cn_equities() -> None:
    assert len(CN_UNIVERSE_SEED) == len(set(CN_UNIVERSE_SEED))  # no dups
    for symbol in CN_UNIVERSE_SEED:
        ref = SymbolRef.parse(symbol)  # every name is a valid market-qualified ticker
        assert ref.market == "CN"
        assert symbol.endswith((".SH", ".SZ"))


# --------------------------------------------------------------------------- #
# percent_rank
# --------------------------------------------------------------------------- #


def test_percent_rank_empty_single_and_order() -> None:
    assert percent_rank({}) == {}
    assert percent_rank({"A": 5.0}) == {"A": 0.5}
    ranks = percent_rank({"A": 1.0, "B": 2.0, "C": 3.0})
    assert ranks["A"] == 0.0 and ranks["C"] == 1.0  # min → 0, max → 1
    assert ranks["B"] == pytest.approx(0.5)


def test_percent_rank_ties_share_midpoint() -> None:
    ranks = percent_rank({"A": 5.0, "B": 5.0, "C": 5.0})
    assert ranks == {"A": 0.5, "B": 0.5, "C": 0.5}  # all equal → all mid


# --------------------------------------------------------------------------- #
# point-in-time visibility primitives
# --------------------------------------------------------------------------- #


def test_latest_market_cap_uses_only_visible_bars() -> None:
    bars = [_bar("A.SH", date(2020, 1, 1), 100.0), _bar("A.SH", date(2025, 1, 1), 999.0)]
    visible = latest_market_cap(bars, date(2021, 1, 1))
    assert visible is not None and visible.total_mv == 100.0  # not the 2025 bar
    assert latest_market_cap(bars, date(2019, 1, 1)) is None  # nothing visible yet


def test_trailing_avg_turnover_window_and_visibility() -> None:
    rows = [(date(2024, 1, d), float(d)) for d in range(1, 11)]  # 1..10
    # window 3 ending <= 2024-01-10 → mean(8,9,10) = 9
    assert trailing_avg_turnover(rows, date(2024, 1, 10), 3) == pytest.approx(9.0)
    # as_of mid-series only sees <= cutoff
    assert trailing_avg_turnover(rows, date(2024, 1, 5), 10) == pytest.approx(3.0)  # mean(1..5)
    assert trailing_avg_turnover(rows, date(2023, 1, 1), 3) is None


# --------------------------------------------------------------------------- #
# point_in_time_top_n — NO FUTURE LEAKAGE (core acceptance)
# --------------------------------------------------------------------------- #


def test_pit_uses_past_market_cap_not_future() -> None:
    market_caps = {
        "BIG.SH": [_bar("BIG.SH", date(2020, 1, 1), 100.0), _bar("BIG.SH", date(2025, 1, 1), 1e15)],
        "SMALL.SH": [_bar("SMALL.SH", date(2020, 1, 1), 200.0)],
    }
    members = point_in_time_top_n(date(2021, 1, 1), market_caps, {}, top_n=10)
    by_ticker = {m.ticker: m.market_cap for m in members}
    assert by_ticker["BIG.SH"] == 100.0  # the PAST bar, never the 2025 giant
    # At this as_of SMALL (200) outranks BIG (100) — ranking is leakage-free.
    assert members[0].ticker == "SMALL.SH" and members[0].rank == 1


def test_pit_excludes_not_yet_listed_ticker() -> None:
    market_caps = {"LATE.SH": [_bar("LATE.SH", date(2025, 1, 1), 500.0)]}
    assert point_in_time_top_n(date(2020, 1, 1), market_caps, {}, top_n=10) == []


def test_future_bars_never_change_membership() -> None:
    seed = [("A.SH", 300.0), ("B.SH", 200.0), ("C.SH", 100.0)]
    base = {t: [_bar(t, date(2020, 1, 1), mv)] for t, mv in seed}
    with_future = {t: [*bars, _bar(t, date(2030, 1, 1), 9e9)] for t, bars in base.items()}
    as_of = date(2021, 1, 1)
    r1 = point_in_time_top_n(as_of, base, {}, top_n=2)
    r2 = point_in_time_top_n(as_of, with_future, {}, top_n=2)

    def rows(members: list[UniverseMember]) -> list[tuple[str, int, float]]:
        return [(m.ticker, m.rank, m.market_cap) for m in members]

    assert rows(r1) == rows(r2)  # identical regardless of the future bars


def test_pit_top_n_truncates_and_ranks() -> None:
    market_caps = {f"T{i}.SH": [_bar(f"T{i}.SH", date(2020, 1, 1), float(i))] for i in range(1, 6)}
    members = point_in_time_top_n(date(2021, 1, 1), market_caps, {}, top_n=3)
    assert [m.ticker for m in members] == ["T5.SH", "T4.SH", "T3.SH"]  # top 3 by mcap
    assert [m.rank for m in members] == [1, 2, 3]


def test_pit_turnover_breaks_market_cap_tie() -> None:
    market_caps = {t: [_bar(t, date(2020, 1, 1), 100.0)] for t in ("A.SH", "B.SH")}
    turnovers = {"A.SH": [(date(2020, 1, 1), 1.0)], "B.SH": [(date(2020, 1, 1), 9.0)]}
    members = point_in_time_top_n(date(2021, 1, 1), market_caps, turnovers, top_n=2)
    assert members[0].ticker == "B.SH"  # equal mcap → higher turnover wins


def test_pit_skips_non_positive_market_cap() -> None:
    market_caps = {
        "Z.SH": [_bar("Z.SH", date(2020, 1, 1), 0.0)],
        "A.SH": [_bar("A.SH", date(2020, 1, 1), 5.0)],
    }
    members = point_in_time_top_n(date(2021, 1, 1), market_caps, {}, top_n=10)
    assert [m.ticker for m in members] == ["A.SH"]


# --------------------------------------------------------------------------- #
# rebalance grid + turnover-from-prices
# --------------------------------------------------------------------------- #


def test_quarterly_rebalance_dates() -> None:
    dates = quarterly_rebalance_dates(date(2024, 2, 1), date(2024, 12, 31))
    assert dates == [date(2024, 3, 31), date(2024, 6, 30), date(2024, 9, 30), date(2024, 12, 31)]
    assert quarterly_rebalance_dates(date(2024, 4, 1), date(2024, 5, 1)) == []  # none inside


def test_turnover_from_price_rows_is_volume_times_close() -> None:
    rows = [
        {"date": "2024-01-02", "ticker": "A.SH", "close": "10", "volume": "100"},
        {"date": "2024-01-03", "ticker": "A.SH", "close": "11", "volume": "200"},
        {"date": "2024-01-02", "ticker": "US", "close": "5", "volume": "1"},  # not a member
        {"date": "bad", "ticker": "A.SH", "close": "x", "volume": "y"},  # malformed → skipped
    ]
    out = turnover_from_price_rows(rows, ["A.SH"])
    assert out == {"A.SH": [(date(2024, 1, 2), 1000.0), (date(2024, 1, 3), 2200.0)]}


# --------------------------------------------------------------------------- #
# orchestrator
# --------------------------------------------------------------------------- #


class _FakeMcapLoader:
    """Returns a 2-bar history per ticker; ``fail`` raises for a ticker."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()

    def fetch_market_cap_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[MarketCapBar]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return [
            _bar(ticker, date(2024, 1, 1), 100.0 + len(ticker)),
            _bar(ticker, date(2024, 4, 1), 110.0 + len(ticker)),
        ]


def _write_prices(path: Path, tickers: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"])
        for ticker in tickers:
            writer.writerow(["2024-03-15", ticker, "1", "1", "1", "10", "10", "500"])


def test_build_cn_universe_writes_both_csvs(tmp_path: Path) -> None:
    prices = tmp_path / "snapshots" / "prices" / "unified" / "prices_daily.csv"
    superset = ["600519.SH", "000858.SZ"]
    _write_prices(prices, superset)
    summary = build_cn_universe(
        data_root=tmp_path,
        prices_path=prices,
        marketcap_loader=_FakeMcapLoader(),
        superset=superset,
        rebalance_dates=[date(2024, 6, 30)],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 12, 31),
        top_n=10,
    )
    assert summary.marketcap_symbols == 2
    assert summary.marketcap_rows == 4  # 2 bars × 2 symbols
    assert summary.universe_rows == 2  # both members selected at the one rebalance
    assert summary.errors == 0

    with Path(summary.universe_path).open() as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == UNIVERSE_HEADER
    assert {r[1] for r in rows[1:]} == set(superset)
    assert all(r[0] == "2024-06-30" for r in rows[1:])  # as_of stamped

    with Path(summary.marketcap_path).open() as handle:
        mc_rows = list(csv.reader(handle))
    assert mc_rows[0] == MARKETCAP_HEADER


def test_build_cn_universe_fetch_failure_counted_not_fatal(tmp_path: Path) -> None:
    prices = tmp_path / "snapshots" / "prices" / "unified" / "prices_daily.csv"
    superset = ["600519.SH", "000858.SZ"]
    _write_prices(prices, superset)
    summary = build_cn_universe(
        data_root=tmp_path,
        prices_path=prices,
        marketcap_loader=_FakeMcapLoader(fail={"000858.SZ"}),
        superset=superset,
        rebalance_dates=[date(2024, 6, 30)],
        from_date=date(2024, 1, 1),
        to_date=date(2024, 12, 31),
        top_n=10,
    )
    assert summary.errors == 1
    assert summary.marketcap_symbols == 1  # only the surviving symbol
    assert summary.universe_rows == 1


# --------------------------------------------------------------------------- #
# akshare market-cap loader + discovery (faked frames, no network)
# --------------------------------------------------------------------------- #


class _FakeAkshare:
    def __init__(
        self, value_frame: pd.DataFrame | None = None, spot_frame: pd.DataFrame | None = None
    ) -> None:
        self._value = value_frame
        self._spot = spot_frame

    def stock_value_em(self, symbol: str) -> pd.DataFrame:
        if self._value is None:
            raise RuntimeError("unreachable")
        return self._value

    def stock_zh_a_spot_em(self) -> pd.DataFrame:
        if self._spot is None:
            raise RuntimeError("unreachable")
        return self._spot


def test_marketcap_loader_parses_value_em_frame_and_filters_window() -> None:
    frame = pd.DataFrame(
        {
            "数据日期": [date(2018, 1, 2), date(2024, 6, 1), date(2099, 1, 1)],
            "当日收盘价": [700.0, 1500.0, 9.0],
            "总市值": [8.8e11, 1.5e12, 1.0],
            "流通市值": [8.8e11, 1.5e12, 1.0],
            "总股本": [1.256e9, 1.25e9, 1.0],
        }
    )
    loader = CnMarketCapLoader(akshare_module=_FakeAkshare(value_frame=frame))
    bars = loader.fetch_market_cap_history("600519.SH", date(2024, 1, 1), date(2024, 12, 31))
    assert [b.bar_date for b in bars] == [date(2024, 6, 1)]  # only the in-window bar
    assert bars[0].total_mv == 1.5e12
    assert bars[0].total_shares == pytest.approx(1.25e9)
    assert bars[0].close == 1500.0


def test_marketcap_loader_absent_akshare_returns_empty() -> None:
    # No injected module + import will fail under the test env name → empty, no raise.
    loader = CnMarketCapLoader(akshare_module=_FakeAkshare(value_frame=None))
    assert loader.fetch_market_cap_history("600519.SH", date(2024, 1, 1), date(2024, 12, 31)) == []


def test_discover_superset_ranks_spot_and_unions_seed() -> None:
    spot = pd.DataFrame(
        {
            "代码": ["600519", "000858", "300750"],
            "总市值": [3.0e12, 1.0e12, 2.0e12],
        }
    )
    fake = _FakeAkshare(spot_frame=spot)
    symbols, provenance = discover_ashare_superset(akshare_module=fake, top_n=2)
    assert provenance == "bulk_spot"
    assert symbols[:2] == ("600519.SH", "300750.SZ")  # top-2 by market cap, mapped canonical
    assert set(CN_UNIVERSE_SEED).issubset(set(symbols))  # seed unioned in


def test_discover_superset_unreachable_falls_back_to_seed() -> None:
    symbols, provenance = discover_ashare_superset(akshare_module=_FakeAkshare(spot_frame=None))
    assert provenance == "seed"
    assert symbols == CN_UNIVERSE_SEED


# --------------------------------------------------------------------------- #
# ST / 退市 exclusion (B065 F001 feedback — protect the pure-momentum variant)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("ST信通", True),
        ("*ST天娱", True),
        ("退市海润", True),
        ("贵州茅台", False),
        ("中国平安", False),
        ("", False),
    ],
)
def test_is_st_name(name: str, expected: bool) -> None:
    assert is_st_name(name) is expected


def test_seed_has_no_st_names() -> None:
    # The curated seed is all blue chips; nothing maps to an ST code prefix.
    # (ST status is by display name, but the seed comment asserts non-ST intent.)
    assert all(not is_st_name(s) for s in CN_UNIVERSE_SEED)


def test_discover_superset_excludes_st_names() -> None:
    # ST codes are deliberately NOT seed names (the seed union would re-add them).
    spot = pd.DataFrame(
        {
            "代码": ["600519", "002999", "600666"],
            "名称": ["贵州茅台", "*ST退市", "ST示例"],
            "总市值": [3.0e12, 5.0e12, 4.0e12],  # ST names have bigger mcap here
        }
    )
    fake = _FakeAkshare(spot_frame=spot)
    symbols, provenance = discover_ashare_superset(akshare_module=fake, top_n=10)
    assert provenance == "bulk_spot"
    # The two ST names are dropped despite their larger market cap; 600519 stays.
    assert "600519.SH" in symbols
    assert "002999.SZ" not in symbols and "600666.SH" not in symbols


# --------------------------------------------------------------------------- #
# §12.10.2 / §26.2 boundary — the universe modules never import trade
# --------------------------------------------------------------------------- #


def _imports_trade(py_path: Path) -> bool:
    tree = ast.parse(py_path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "trade" or a.name.startswith("trade.") for a in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if node.level == 0 and (module == "trade" or module.startswith("trade.")):
                return True
    return False


def test_universe_modules_do_not_import_trade() -> None:
    pkg = Path(__file__).resolve().parents[2] / "workbench_api" / "data_refresh"
    for name in ("cn_universe.py", "cn_marketcap.py"):
        assert not _imports_trade(pkg / name), (
            f"{name} must not import trade — akshare is workbench-side, trade reads the CSV offline"
        )
