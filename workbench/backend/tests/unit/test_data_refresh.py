"""B045 F001 — real-data refresh CLI + unified CSV writer.

Covers run_refresh writing the two unified CSVs in the EXACT schema the trade
loaders read (asserted against trade's UNIFIED_REQUIRED_COLUMNS /
UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS), per-symbol failure resilience,
synthetic-ticker skip, the universe composition, and the CLI wiring.

Loaders are faked (no network / secret); the real Tiingo + SEC EDGAR loaders
are exercised at L2 on the VM. Tests assert schema/wiring, not market values
(v0.9.21 fixture-vs-real signal).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from workbench_api.data.snapshot_loader import PriceBar
from workbench_api.data_refresh import cli as refresh_cli
from workbench_api.data_refresh.refresh import (
    CN_HK_UNIVERSE,
    ETF_UNIVERSE,
    FUNDAMENTALS_HEADER,
    PRICES_HEADER,
    RefreshSummary,
    currency_for_symbol,
    equity_universe,
    price_universe,
    run_refresh,
)

_FROM = date(2023, 1, 1)
_TO = date(2024, 12, 31)


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


def _companyfacts(ticker: str) -> dict[str, Any]:
    """Minimal live-shape SEC companyfacts that synthesises exactly one quarter
    (2024Q3). ``filed`` is 2024-12-31 to match the fake price bar's date so the
    MarketCap close resolves (the ratio math itself is covered exhaustively by
    test_backfill_fundamentals.py; here we verify the refresh WIRING)."""

    def entry(val: float) -> dict[str, Any]:
        return {
            "end": "2024-09-30",
            "val": val,
            "filed": "2024-12-31",
            "fy": 2024,
            "fp": "Q3",
            "form": "10-Q",
            "accn": "0000000000-24-000001",
        }

    def usd(val: float) -> dict[str, Any]:
        return {"units": {"USD": [entry(val)]}}

    def shares(val: float) -> dict[str, Any]:
        return {"units": {"shares": [entry(val)]}}

    return {
        "cik": 111,
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": usd(1_000_000.0),
                "StockholdersEquity": usd(5_000_000.0),
                "Revenues": usd(10_000_000.0),
                "CostOfGoodsAndServicesSold": usd(6_000_000.0),
                "NetCashProvidedByUsedInOperatingActivities": usd(2_000_000.0),
                "PaymentsToAcquirePropertyPlantAndEquipment": usd(500_000.0),
                "LongTermDebt": usd(3_000_000.0),
                "Assets": usd(20_000_000.0),
                "CashAndCashEquivalentsAtCarryingValue": usd(1_000_000.0),
                "OperatingIncomeLoss": usd(2_500_000.0),
                "DepreciationDepletionAndAmortization": usd(400_000.0),
            },
            "dei": {"CommonStockSharesOutstanding": shares(1_000_000.0)},
        },
    }


class _FakePrices:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()

    def fetch_daily_bars(self, ticker: str, from_date: date, to_date: date) -> list[PriceBar]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return [_bar(ticker)]


class _FakeFundamentals:
    """Fake SEC loader matching the live interface refresh now uses:
    ``ticker_cik_map`` (synthetic → CIK None) + ``fetch_raw_companyfacts``."""

    def __init__(self, synthetic: set[str] | None = None, fail: set[str] | None = None) -> None:
        self.synthetic = synthetic or set()
        self.fail = fail or set()

    @property
    def ticker_cik_map(self) -> dict[str, int | None]:
        out: dict[str, int | None] = {ticker: 111 for ticker in equity_universe()}
        for ticker in self.synthetic:
            out[ticker] = None
        return out

    def fetch_raw_companyfacts(self, ticker: str) -> dict[str, Any]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return _companyfacts(ticker)


class _FakeCnHk:
    """Fake CN/HK akshare-backed loader (no network); 1 bar per requested ticker."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()

    def fetch_daily_bars(self, ticker: str, from_date: date, to_date: date) -> list[PriceBar]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        return [_bar(ticker)]


class _FakeFx:
    """Fake FRED FX loader (no key/network); returns no points by default."""

    def fetch_fx(self, series_id: str, *, limit: int) -> list[Any]:
        return []


def _run(
    tmp_path: Path,
    *,
    prices_loader: _FakePrices | None = None,
    fundamentals_loader: _FakeFundamentals | None = None,
    cn_hk_prices_loader: _FakeCnHk | None = None,
) -> RefreshSummary:
    return run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=prices_loader or _FakePrices(),
        fundamentals_loader=fundamentals_loader or _FakeFundamentals(),
        cn_hk_prices_loader=cn_hk_prices_loader,
    )


# --- universe ---


def test_price_universe_is_etfs_plus_equities_sorted_unique() -> None:
    universe = price_universe()
    assert set(ETF_UNIVERSE).issubset(set(universe))
    assert set(equity_universe()).issubset(set(universe))
    assert list(universe) == sorted(set(universe))  # sorted + de-duplicated
    assert len(universe) == len(set(universe))


def test_etf_universe_includes_hk_china_phase1_etfs() -> None:
    """BL-B011-S2 F001 — the HK-China satellite Phase 1 ETFs are priced by
    the refresh pipeline so the hk_china loader resolves real data."""

    assert {"MCHI", "FXI", "KWEB", "ASHR"}.issubset(set(ETF_UNIVERSE))


# --- prices CSV ---


def test_prices_csv_written_with_exact_trade_schema(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    path = Path(summary.prices_path)
    assert path.exists()
    with path.open() as handle:
        rows = list(csv.reader(handle))
    assert rows[0] == PRICES_HEADER
    # Schema-compat with the trade loader's required columns.
    from trade.data.loader import UNIFIED_REQUIRED_COLUMNS  # type: ignore[import-untyped]

    assert UNIFIED_REQUIRED_COLUMNS.issubset(set(rows[0]))
    assert summary.price_rows == len(price_universe())  # 1 bar per symbol
    # A sample data row: date ISO + ticker present.
    assert rows[1][0] == "2024-12-31"


def test_price_fetch_failure_is_counted_not_fatal(tmp_path: Path) -> None:
    failing = next(iter(price_universe()))
    summary = _run(tmp_path, prices_loader=_FakePrices(fail={failing}))
    assert summary.errors >= 1
    # The other symbols still wrote rows.
    assert summary.price_rows == len(price_universe()) - 1
    assert Path(summary.prices_path).exists()


# --- fundamentals CSV ---


def test_fundamentals_csv_written_with_exact_trade_schema(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    path = Path(summary.fundamentals_path)
    assert path.exists()
    with path.open() as handle:
        rows = list(csv.reader(handle))
    from trade.data.loader import (
        UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS,
    )

    # Exact header + order match the trade loader's required columns.
    assert rows[0] == FUNDAMENTALS_HEADER
    assert tuple(rows[0]) == tuple(UNIFIED_FUNDAMENTALS_REQUIRED_COLUMNS)
    # Fundamentals are fetched for equities only (not ETFs).
    assert summary.fundamental_symbols == len(equity_universe())
    assert summary.fundamental_rows == len(equity_universe())


def test_synthetic_ticker_fundamentals_skipped_not_error(tmp_path: Path) -> None:
    # A synthetic ticker raises ValueError in the loader → skipped, not an error.
    one_equity = next(iter(equity_universe()))
    summary = _run(tmp_path, fundamentals_loader=_FakeFundamentals(synthetic={one_equity}))
    assert summary.errors == 0
    assert summary.fundamental_rows == len(equity_universe()) - 1


# --- B062 F002: A-share + HK rows + US-zero-regression ---


def test_cn_hk_none_is_us_only_backward_compat(tmp_path: Path) -> None:
    summary = _run(tmp_path)  # no cn_hk loader
    assert summary.cn_hk_symbols == 0
    assert summary.cn_hk_rows == 0
    assert summary.price_rows == len(price_universe())


def test_cn_hk_rows_appended_without_touching_us_rows(tmp_path: Path) -> None:
    # US-only baseline.
    base = _run(tmp_path / "us")
    with Path(base.prices_path).open() as handle:
        us_rows = list(csv.reader(handle))
    # US + CN/HK.
    both = _run(tmp_path / "both", cn_hk_prices_loader=_FakeCnHk())
    with Path(both.prices_path).open() as handle:
        both_rows = list(csv.reader(handle))

    # ★US-zero-regression: the header + every US row is byte-identical and in the
    # same position; CN/HK are strictly appended after.
    assert both_rows[: len(us_rows)] == us_rows
    assert both.price_rows == base.price_rows  # US count unchanged
    assert both.cn_hk_symbols == len(CN_HK_UNIVERSE)
    assert both.cn_hk_rows == len(CN_HK_UNIVERSE)
    appended_tickers = {row[1] for row in both_rows[len(us_rows):]}
    assert appended_tickers == set(CN_HK_UNIVERSE)
    # Schema unchanged — still the exact 8-column trade schema (no currency col).
    assert both_rows[0] == PRICES_HEADER


def test_cn_hk_fetch_failure_counted_not_fatal(tmp_path: Path) -> None:
    summary = _run(tmp_path, cn_hk_prices_loader=_FakeCnHk(fail={"0700.HK"}))
    assert summary.errors >= 1
    assert summary.cn_hk_rows == len(CN_HK_UNIVERSE) - 1
    # US rows are unaffected by a CN/HK failure.
    assert summary.price_rows == len(price_universe())


def test_currency_for_symbol_derives_from_ticker() -> None:
    assert currency_for_symbol("AAPL") == "USD"
    assert currency_for_symbol("600519.SH") == "CNY"
    assert currency_for_symbol("0700.HK") == "HKD"


def test_cn_hk_universe_is_ashare_plus_hk() -> None:
    hk = {s for s in CN_HK_UNIVERSE if s.endswith(".HK")}
    cn = {s for s in CN_HK_UNIVERSE if s.endswith((".SH", ".SZ"))}
    assert hk and cn  # both markets represented
    assert hk | cn == set(CN_HK_UNIVERSE)  # nothing else


def test_etfs_have_no_fundamentals_rows(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    with Path(summary.fundamentals_path).open() as handle:
        rows = list(csv.reader(handle))
    tickers = {r[1] for r in rows[1:]}
    assert tickers.isdisjoint(set(ETF_UNIVERSE))  # no ETF fundamentals


# --- CSV layout + CLI wiring ---


def test_csv_layout_matches_trade_loader_relpaths(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    prices_expected = tmp_path / "snapshots" / "prices" / "unified" / "prices_daily.csv"
    assert Path(summary.prices_path) == prices_expected
    assert (
        Path(summary.fundamentals_path)
        == tmp_path / "snapshots" / "fundamentals" / "unified" / "fundamentals.csv"
    )


def test_cli_fetch_main_writes_both_csvs(tmp_path: Path) -> None:
    args = refresh_cli.parse_args(["fetch", "--data-root", str(tmp_path), "--lookback-days", "400"])
    summary = refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk(), _FakeFx()),
        today=date(2024, 12, 31),
    )
    assert summary.price_rows > 0
    assert summary.fundamental_rows > 0
    assert summary.cn_hk_rows == len(CN_HK_UNIVERSE)  # B062 F002 wiring
    assert Path(summary.prices_path).exists()
    assert Path(summary.fundamentals_path).exists()


def test_cli_default_data_root_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", "/var/lib/workbench/data")
    args = refresh_cli.parse_args(["fetch"])
    assert str(args.data_root) == "/var/lib/workbench/data"


# --- B065 F001: A-share universe superset price EXTENSION + US/CN_HK zero-regression ---


def test_cn_extra_none_is_backward_compat(tmp_path: Path) -> None:
    summary = _run(tmp_path, cn_hk_prices_loader=_FakeCnHk())  # no extra symbols
    assert summary.cn_universe_price_symbols == 0
    assert summary.cn_universe_price_rows == 0


def test_cn_extra_appends_new_rows_without_touching_us_or_cn_hk(tmp_path: Path) -> None:
    # Baseline: US + CN_HK only.
    base = run_refresh(
        data_root=tmp_path / "base",
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_hk_prices_loader=_FakeCnHk(),
    )
    with Path(base.prices_path).open() as handle:
        base_rows = list(csv.reader(handle))

    # + an A-share superset: one name already in CN_HK (deduped) + two new names.
    extra = ["600519.SH", "600999.SH", "000001.SZ"]
    both = run_refresh(
        data_root=tmp_path / "both",
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_hk_prices_loader=_FakeCnHk(),
        cn_extra_price_symbols=extra,
    )
    with Path(both.prices_path).open() as handle:
        both_rows = list(csv.reader(handle))

    # 600519.SH is already in CN_HK_UNIVERSE → not re-fetched; only the 2 new ones.
    assert both.cn_universe_price_symbols == 2
    assert both.cn_universe_price_rows == 2
    # ★US + CN_HK rows are byte-identical and in the same position; extras append after.
    assert both_rows[: len(base_rows)] == base_rows
    appended = {row[1] for row in both_rows[len(base_rows):]}
    assert appended == {"600999.SH", "000001.SZ"}


def test_cn_extra_without_cn_hk_loader_is_noop(tmp_path: Path) -> None:
    # The extension reuses the cn_hk loader to fetch; no loader → nothing fetched.
    summary = run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_hk_prices_loader=None,
        cn_extra_price_symbols=["600999.SH"],
    )
    assert summary.cn_universe_price_symbols == 0
    assert summary.price_rows == len(price_universe())


def test_cn_extra_fetch_failure_counted_not_fatal(tmp_path: Path) -> None:
    summary = run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_hk_prices_loader=_FakeCnHk(fail={"600999.SH"}),
        cn_extra_price_symbols=["600999.SH", "000001.SZ"],
    )
    assert summary.errors >= 1
    assert summary.cn_universe_price_rows == 1  # the surviving extra still wrote


class _FakeMcap:
    """Fake market-cap loader for the cli universe-build wiring test."""

    def fetch_market_cap_history(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[Any]:
        from workbench_api.data_refresh.cn_universe import MarketCapBar

        return [MarketCapBar(ticker=ticker, bar_date=date(2024, 6, 1), total_mv=1.0e12)]


def test_cli_fetch_main_builds_cn_universe(tmp_path: Path) -> None:
    args = refresh_cli.parse_args(["fetch", "--data-root", str(tmp_path), "--lookback-days", "400"])
    superset = ["600519.SH", "600999.SH"]  # 600519 in CN_HK (deduped), 600999 new
    summary = refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk(), _FakeFx()),
        today=date(2024, 12, 31),
        cn_universe_loader=_FakeMcap(),
        superset_provider=lambda: superset,
    )
    # US refresh unaffected; universe artifact written.
    assert summary.price_rows == len(price_universe())
    universe_csv = tmp_path / "snapshots" / "universe" / "cn_pit_universe.csv"
    marketcap_csv = tmp_path / "snapshots" / "universe" / "cn_marketcap.csv"
    assert universe_csv.exists() and marketcap_csv.exists()
    with universe_csv.open() as handle:
        rows = list(csv.reader(handle))
    members = {r[1] for r in rows[1:]}
    assert members == set(superset)  # both ranked at each quarterly rebalance


def test_cli_no_cn_universe_flag_skips_build(tmp_path: Path) -> None:
    args = refresh_cli.parse_args(
        ["fetch", "--data-root", str(tmp_path), "--lookback-days", "400", "--no-cn-universe"]
    )
    refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk(), _FakeFx()),
        today=date(2024, 12, 31),
        cn_universe_loader=_FakeMcap(),
        superset_provider=lambda: ["600519.SH"],
    )
    assert not (tmp_path / "snapshots" / "universe" / "cn_pit_universe.csv").exists()


# --- B065 F002: A-share CAS fundamentals appended + US-zero-regression ---


def _cn_fundamentals_row(ticker: str) -> dict[str, Any]:
    """One unified-schema CN fundamentals row (all 12 columns keyed)."""

    return {
        "report_date": "2024-10-31",
        "ticker": ticker,
        "fiscal_quarter": "2024Q3",
        "fiscal_quarter_end": "2024-09-30",
        "roe": 0.24,
        "gross_margin": 0.90,
        "fcf_yield": 0.03,
        "debt_to_assets": 0.13,
        "pe": 19.0,
        "pb": 6.0,
        "ev_ebitda": None,
        "earnings_yield": 0.05,
    }


class _FakeCnFundamentals:
    """Fake CAS fundamentals loader; ``fail`` raises, others yield 2 rows."""

    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()

    def fetch_fundamentals_rows(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        if ticker in self.fail:
            raise RuntimeError(f"boom {ticker}")
        q3 = _cn_fundamentals_row(ticker)
        return [q3, {**q3, "fiscal_quarter": "2024Q2"}]


def test_cn_fundamentals_appended_after_us_rows(tmp_path: Path) -> None:
    base = run_refresh(
        data_root=tmp_path / "base",
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
    )
    with Path(base.fundamentals_path).open() as handle:
        us_rows = list(csv.reader(handle))

    both = run_refresh(
        data_root=tmp_path / "both",
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_fundamentals_loader=_FakeCnFundamentals(),
        cn_fundamentals_symbols=["600519.SH", "000001.SZ"],
    )
    with Path(both.fundamentals_path).open() as handle:
        both_rows = list(csv.reader(handle))

    # ★US SEC rows byte-identical + in the same position; CN rows strictly after.
    assert both_rows[: len(us_rows)] == us_rows
    assert both.fundamental_rows == base.fundamental_rows  # US count unchanged
    assert both.cn_fundamental_symbols == 2
    assert both.cn_fundamental_rows == 4  # 2 rows × 2 symbols
    appended_tickers = {row[1] for row in both_rows[len(us_rows):]}
    assert appended_tickers == {"600519.SH", "000001.SZ"}
    # ev_ebitda None → empty CSV cell (column 11), schema unchanged.
    assert both_rows[0] == FUNDAMENTALS_HEADER
    assert both_rows[len(us_rows)][10] == ""  # ev_ebitda empty


def test_cn_fundamentals_none_is_backward_compat(tmp_path: Path) -> None:
    summary = _run(tmp_path)
    assert summary.cn_fundamental_symbols == 0
    assert summary.cn_fundamental_rows == 0


def test_cn_fundamentals_fetch_failure_counted_not_fatal(tmp_path: Path) -> None:
    summary = run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_fundamentals_loader=_FakeCnFundamentals(fail={"000001.SZ"}),
        cn_fundamentals_symbols=["600519.SH", "000001.SZ"],
    )
    assert summary.errors >= 1
    assert summary.cn_fundamental_rows == 2  # only the surviving symbol's rows


def test_cli_fetch_main_writes_cn_fundamentals(tmp_path: Path) -> None:
    args = refresh_cli.parse_args(["fetch", "--data-root", str(tmp_path), "--lookback-days", "400"])
    summary = refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk(), _FakeFx()),
        today=date(2024, 12, 31),
        cn_universe_loader=_FakeMcap(),
        superset_provider=lambda: ["600519.SH", "000001.SZ"],
        cn_fundamentals_loader=_FakeCnFundamentals(),
    )
    assert summary.cn_fundamental_symbols == 2
    assert summary.cn_fundamental_rows == 4
    # US fundamentals untouched.
    assert summary.fundamental_rows == len(equity_universe())


# --- B075 F001: wide-universe ungate + fundamentals decouple + partial-failure ---


def test_b075_new_cli_flags_default_off_and_wide_target_n() -> None:
    """The wide-universe / decouple flags default OFF (pre-B075 behaviour) and the
    universe sizing defaults to the feasibility-gated target N (spec §2 F001)."""

    args = refresh_cli.parse_args(["fetch"])
    assert args.cn_universe_sina_fallback is False
    assert args.no_cn_universe_build is False
    assert args.no_cn_fundamentals is False
    assert args.cn_universe_top_n == refresh_cli.WIDE_UNIVERSE_TARGET_N
    assert args.cn_universe_max_superset == refresh_cli.WIDE_UNIVERSE_TARGET_N
    assert refresh_cli.WIDE_UNIVERSE_TARGET_N == 1500

    flagged = refresh_cli.parse_args(
        ["fetch", "--cn-universe-sina-fallback", "--no-cn-universe-build", "--no-cn-fundamentals"]
    )
    assert flagged.cn_universe_sina_fallback is True
    assert flagged.no_cn_universe_build is True
    assert flagged.no_cn_fundamentals is True


def test_b075_no_cn_universe_build_keeps_wide_prices_but_skips_build(tmp_path: Path) -> None:
    """The daily timer path: wide A-share PRICES are still fetched (the 命门) but
    the heavy historical-mcap universe build is skipped (decoupled to a low-freq
    job). The PIT universe CSV is left untouched; prices are written."""

    args = refresh_cli.parse_args(
        ["fetch", "--data-root", str(tmp_path), "--lookback-days", "400", "--no-cn-universe-build"]
    )
    superset = ["600519.SH", "600999.SH", "000001.SZ"]  # 600519 in CN_HK → deduped
    summary = refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk(), _FakeFx()),
        today=date(2024, 12, 31),
        cn_universe_loader=_FakeMcap(),
        superset_provider=lambda: superset,
        cn_fundamentals_loader=_FakeCnFundamentals(),
    )
    # Wide prices fetched for the two NEW names (600519 deduped against CN_HK).
    assert summary.cn_universe_price_symbols == 2
    assert summary.cn_universe_price_rows == 2
    # The expensive PIT universe build was skipped — no membership artifact written.
    assert not (tmp_path / "snapshots" / "universe" / "cn_pit_universe.csv").exists()
    assert not (tmp_path / "snapshots" / "universe" / "cn_marketcap.csv").exists()


def test_b075_no_cn_fundamentals_skips_fundamentals_but_builds_universe(tmp_path: Path) -> None:
    """The fundamentals decouple: CAS fundamentals are skipped (low-freq job owns
    them) while the universe build + wide prices still run."""

    args = refresh_cli.parse_args(
        ["fetch", "--data-root", str(tmp_path), "--lookback-days", "400", "--no-cn-fundamentals"]
    )
    summary = refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk(), _FakeFx()),
        today=date(2024, 12, 31),
        cn_universe_loader=_FakeMcap(),
        superset_provider=lambda: ["600519.SH", "600999.SH"],
        cn_fundamentals_loader=_FakeCnFundamentals(),
    )
    # CN fundamentals skipped this run.
    assert summary.cn_fundamental_symbols == 0
    assert summary.cn_fundamental_rows == 0
    # US fundamentals untouched (decouple is CN-only).
    assert summary.fundamental_rows == len(equity_universe())
    # Universe build still ran (it is independently gated).
    assert (tmp_path / "snapshots" / "universe" / "cn_pit_universe.csv").exists()


def test_b075_daily_path_wide_prices_no_build_no_fundamentals(tmp_path: Path) -> None:
    """Both decouple flags together = the production DAILY job shape: wide prices
    only, no build, no CN fundamentals."""

    args = refresh_cli.parse_args(
        [
            "fetch",
            "--data-root",
            str(tmp_path),
            "--lookback-days",
            "400",
            "--no-cn-universe-build",
            "--no-cn-fundamentals",
        ]
    )
    summary = refresh_cli.fetch_main(
        args,
        loader_factory=lambda: (_FakePrices(), _FakeFundamentals(), _FakeCnHk(), _FakeFx()),
        today=date(2024, 12, 31),
        cn_universe_loader=_FakeMcap(),
        superset_provider=lambda: ["600999.SH", "000001.SZ"],
        cn_fundamentals_loader=_FakeCnFundamentals(),
    )
    assert summary.cn_universe_price_rows == 2  # wide prices fetched
    assert summary.cn_fundamental_rows == 0  # no fundamentals
    assert not (tmp_path / "snapshots" / "universe" / "cn_pit_universe.csv").exists()
    # US refresh fully intact (zero-regression).
    assert summary.price_rows == len(price_universe())
    assert summary.fundamental_rows == len(equity_universe())


def test_b075_wide_block_errors_tracked_separately_from_core(tmp_path: Path) -> None:
    """Wide A-share price + fundamentals failures increment their own counters AND
    the shared ``errors`` total (one error contract)."""

    summary = run_refresh(
        data_root=tmp_path,
        from_date=_FROM,
        to_date=_TO,
        prices_loader=_FakePrices(),
        fundamentals_loader=_FakeFundamentals(),
        cn_hk_prices_loader=_FakeCnHk(fail={"600999.SH"}),
        cn_extra_price_symbols=["600999.SH", "000001.SZ"],
        cn_fundamentals_loader=_FakeCnFundamentals(fail={"000001.SZ"}),
        cn_fundamentals_symbols=["600519.SH", "000001.SZ"],
    )
    assert summary.cn_universe_price_errors == 1
    assert summary.cn_fundamental_errors == 1
    # Both also counted in the shared total alongside any core errors (here 0 core).
    assert summary.errors == 2
    # Survivors still written (不炸整轮).
    assert summary.cn_universe_price_rows == 1
    assert summary.cn_fundamental_rows == 2


def _summary(
    *,
    errors: int,
    cn_price_symbols: int = 0,
    cn_price_errors: int = 0,
    cn_fund_symbols: int = 0,
    cn_fund_errors: int = 0,
) -> RefreshSummary:
    return RefreshSummary(
        price_symbols=10,
        price_rows=10,
        fundamental_symbols=5,
        fundamental_rows=5,
        errors=errors,
        prices_path="p",
        fundamentals_path="f",
        cn_universe_price_symbols=cn_price_symbols,
        cn_universe_price_errors=cn_price_errors,
        cn_fundamental_symbols=cn_fund_symbols,
        cn_fundamental_errors=cn_fund_errors,
    )


def test_b075_exit_decision_clean_run_is_zero() -> None:
    decision = refresh_cli.resolve_exit_decision(_summary(errors=0))
    assert decision.exit_code == 0


def test_b075_exit_decision_core_error_is_strict() -> None:
    # A US/CN_HK failure with no wide errors → core_errors=1 → fail.
    decision = refresh_cli.resolve_exit_decision(_summary(errors=1))
    assert decision.core_errors == 1
    assert decision.exit_code == 1


def test_b075_exit_decision_tolerates_bounded_wide_tail() -> None:
    # 30 wide names attempted, 3 failed (10%) ≤ 20% floor, 0 core → tolerated.
    decision = refresh_cli.resolve_exit_decision(
        _summary(errors=3, cn_price_symbols=30, cn_price_errors=3)
    )
    assert decision.core_errors == 0
    assert decision.wide_errors == 3
    assert decision.wide_block_failed is False
    assert decision.exit_code == 0


def test_b075_exit_decision_fails_when_wide_rate_over_floor() -> None:
    # 10 wide names, 5 failed (50%) > 20% floor → a real outage → fail.
    decision = refresh_cli.resolve_exit_decision(
        _summary(errors=5, cn_fund_symbols=10, cn_fund_errors=5)
    )
    assert decision.core_errors == 0
    assert decision.wide_failure_rate == 0.5
    assert decision.wide_block_failed is True
    assert decision.exit_code == 1


def test_b075_exit_decision_core_error_fails_even_if_wide_within_floor() -> None:
    # 1 core error + a tolerable wide tail → still fail on the core error.
    decision = refresh_cli.resolve_exit_decision(
        _summary(errors=2, cn_price_symbols=30, cn_price_errors=1)
    )
    assert decision.core_errors == 1
    assert decision.wide_block_failed is False
    assert decision.exit_code == 1
