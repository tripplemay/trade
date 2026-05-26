"""B028 F002 — master ticker universe for the Real Data Backfill.

Single source of truth for the ticker set ``scripts/backfill_prices.py``
runs through Tiingo. Aggregates:

* **Master 4-sleeve ETF coverage** — the index proxies the B011 master
  portfolio rotates between (broad equity, growth, intermediate bonds,
  cash-like, gold, small-cap, international, emerging, long bonds).
* **B025 US Quality Momentum satellite tickers** — the 27 real-listed
  large-caps from ``data/fixtures/us_quality_momentum/universe.csv``.
  The 3 synthetic ``ZQ*`` fixture tickers are intentionally excluded
  because Tiingo / Yahoo will not resolve them.
* **US-listed ADR proxies** — the standard set the workbench may
  surface when discussing HK-China exposure (per
  ``docs/product/data-source-evaluation-2026-05.md`` §9 ADR proxy
  invariant). Native HK tickers are out of scope (永久边界 — see B011).

Maintenance:
* Adding a ticker that's already in B025 fixture is fine; the union
  semantics dedupe at load time.
* Don't list synthetic ``ZQ*`` tickers here. They live only in
  fixtures and will fail every real-data adapter.
* Production cost is bounded by ``MonthlyBudgetGuard`` (B027): the
  full universe × one fetch each is ~50-60 Tiingo requests, well
  under the Starter tier's 60 req/hour rate limit and the $10/month
  budget cap.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd  # type: ignore[import-untyped]

# B011 Master Portfolio sleeve ETFs + adjacent high-volume index proxies
# commonly held alongside the sleeve. The extra 5 (VTI / AGG / BIL / VEA /
# VWO) bring the master universe into the 50-80 floor the spec asks for,
# and they're the natural companions B013 regime-adaptive / B016 HRP would
# reach for when expanded.
MASTER_SLEEVE_ETFS: tuple[str, ...] = (
    "SPY",   # S&P 500 — broad US equity sleeve
    "QQQ",   # NASDAQ-100 — growth tilt
    "IEF",   # 7-10 yr Treasury — intermediate bond sleeve
    "SGOV",  # 0-3 mo Treasury — cash-like
    "GLD",   # gold — diversifier
    "IWM",   # Russell 2000 — small-cap
    "EFA",   # MSCI EAFE — international developed
    "EEM",   # MSCI EM — emerging markets
    "TLT",   # 20+ yr Treasury — long-duration bond
    "VTI",   # total US stock market — broad-equity sleeve alt
    "AGG",   # US aggregate bond — total-bond complement
    "BIL",   # 1-3 mo Treasury — cash-like alt
    "VEA",   # FTSE developed ex-US — international developed alt
    "VWO",   # FTSE emerging — EM alt
)

# B025 US Quality Momentum 30-ticker fixture, minus the 3 synthetic
# ``ZQ*`` tickers that exist only in the fixture (real-vendor lookup
# would fail for them). See ``data/fixtures/us_quality_momentum/universe.csv``
# for the on-disk source of truth.
B025_US_QUALITY_REAL_TICKERS: tuple[str, ...] = (
    "AAPL", "AMT", "AMZN", "APD", "BAC", "CAT", "CVX", "DUK", "ECL",
    "GOOGL", "HD", "HON", "JNJ", "JPM", "KO", "LIN", "META", "MSFT",
    "NEE", "NVDA", "PG", "PLD", "UNH", "UPS", "V", "WMT", "XOM",
)

# US-listed China / HK ADR proxies. The workbench surfaces these when
# discussing Greater China exposure; native HK tickers stay out of
# scope (data-source-evaluation §9 永久边界).
US_LISTED_ADR_PROXIES: tuple[str, ...] = (
    "FXI",    # iShares China Large-Cap ETF
    "MCHI",   # iShares MSCI China ETF
    "KWEB",   # KraneShares CSI China Internet ETF
    "EWH",    # iShares MSCI Hong Kong ETF
    "BABA",   # Alibaba Group
    "PDD",    # PDD Holdings (Pinduoduo)
    "NTES",   # NetEase
    "TCEHY",  # Tencent OTC ADR
    "NIO",    # NIO Inc.
    "XPEV",   # XPeng Inc.
    "LI",     # Li Auto Inc.
)


def master_universe() -> list[str]:
    """Return the deduplicated master ticker universe in stable order.

    The order is: Master sleeve ETFs first, then B025 real tickers,
    then ADR proxies — chosen so a partial backfill that's interrupted
    by network issues still gets the highest-value tickers first.
    """

    out: list[str] = []
    for source in (
        MASTER_SLEEVE_ETFS,
        B025_US_QUALITY_REAL_TICKERS,
        US_LISTED_ADR_PROXIES,
    ):
        for ticker in source:
            if ticker not in out:
                out.append(ticker)
    return out


def load_b025_real_tickers_from_fixture(
    fixture_path: Path | None = None,
) -> list[str]:
    """Re-resolve the B025 real-ticker subset by reading the fixture.

    Useful when the fixture grows / shrinks and we want to keep the
    universe in lockstep automatically. Filters synthetic ``ZQ*``
    tickers the same way the static constant above does.
    """

    repo_root = Path(__file__).resolve().parents[1]
    target = fixture_path or (
        repo_root / "data" / "fixtures" / "us_quality_momentum" / "universe.csv"
    )
    df = pd.read_csv(target)
    return [t for t in sorted(df["ticker"].unique()) if not t.startswith("ZQ")]


def assert_master_universe_consistent_with_fixture() -> None:
    """Pin the static B025 list against the on-disk fixture.

    Raises ``AssertionError`` if the two drift — e.g. the fixture
    adds a real ticker we forgot to mirror here. This is the
    consistency assert the unit test calls.
    """

    fixture_set = set(load_b025_real_tickers_from_fixture())
    declared_set = set(B025_US_QUALITY_REAL_TICKERS)
    fixture_minus_declared = sorted(fixture_set - declared_set)
    declared_minus_fixture = sorted(declared_set - fixture_set)
    if fixture_minus_declared or declared_minus_fixture:
        raise AssertionError(
            "scripts/universe_master.py B025_US_QUALITY_REAL_TICKERS drifted "
            "from data/fixtures/us_quality_momentum/universe.csv. "
            f"Fixture only: {fixture_minus_declared}; "
            f"declared only: {declared_minus_fixture}. Reconcile both sides."
        )


if __name__ == "__main__":
    tickers = master_universe()
    print(f"Master universe size: {len(tickers)}")
    for t in tickers:
        print(t)
