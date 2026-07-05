#!/usr/bin/env python
"""B092 F001 — fetch a ~100-name S&P-100-style US universe for the attack first-look.

Research-only (touches NO strategy/production/Master code, NO data_root). Fetches:

  * PRICES: qfq-adjusted daily bars for ~100 mega/large-caps + SPY baseline via
    ``akshare.stock_us_daily(symbol=<TICKER>, adjust='qfq')`` (free, no key — same
    source B090 used). akshare returns qfq ``close`` only, so ``adj_close`` is set
    equal to the qfq close (total-return-ish; NOT identical to a vendor adj_close —
    honest caveat carried from B090). Resilient: a ticker that 404s / errors is
    logged + skipped, coverage reported.
  * FUNDAMENTALS (quality source): SEC EDGAR ``companyfacts`` JSON (free, needs a
    User-Agent). Ticker->CIK via https://www.sec.gov/files/company_tickers.json.
    For each ANNUAL (10-K, fp=FY) period we extract NetIncomeLoss (duration),
    StockholdersEquity + Liabilities (instant) keyed by period-end date, plus the
    SEC ``filed`` date. That ``filed`` date is what makes the downstream quality
    filter POINT-IN-TIME: a rebalance on date t may only use annual filings with
    ``filed <= t`` (no look-ahead). ROE = NetIncome / Equity; debt_to_equity =
    Liabilities / Equity.

Outputs cached under ``data/research/b092_us/`` (gitignored) so re-runs resume:
  * ``by_ticker/<T>.csv``          — per-ticker normalized OHLCV
  * ``unified_prices.csv``         — all covered tickers, long format
  * ``sec_raw/<T>.json``           — raw companyfacts (cache; skip re-fetch)
  * ``fundamentals_annual.csv``    — ticker,period_end,filed,net_income,equity,
                                      liabilities,roe,debt_to_equity

Run:  workbench/backend/.venv/bin/python -m scripts.research.b092_us_universe_fetch
"""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

_OUT_DIR = Path("data/research/b092_us")
_BY_TICKER_DIR = _OUT_DIR / "by_ticker"
_SEC_RAW_DIR = _OUT_DIR / "sec_raw"
_UNIFIED_CSV = _OUT_DIR / "unified_prices.csv"
_FUNDAMENTALS_CSV = _OUT_DIR / "fundamentals_annual.csv"

_PRICE_COLUMNS: tuple[str, ...] = (
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
)
_FUNDAMENTALS_COLUMNS: tuple[str, ...] = (
    "ticker",
    "period_end",
    "filed",
    "net_income",
    "equity",
    "liabilities",
    "roe",
    "debt_to_equity",
)

_SEC_USER_AGENT = "b092-research brady.husband9068@yahoo.com"
_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# ~100-name S&P-100-style liquid mega/large-cap universe (dotted tickers such as
# BRK.B avoided — akshare's symbol form is unreliable for them). SPY is fetched
# separately as a baseline and is NOT part of the selection universe.
US100: tuple[str, ...] = (
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "ORCL",
    "CRM", "ADBE", "CSCO", "ACN", "AMD", "QCOM", "TXN", "INTC", "IBM", "INTU",
    "NOW", "AMAT", "MU", "CMCSA", "NFLX", "PYPL", "JPM", "V", "MA", "BAC",
    "WFC", "GS", "MS", "AXP", "BLK", "SPGI", "C", "SCHW", "USB", "PNC", "CB",
    "UNH", "JNJ", "LLY", "MRK", "ABBV", "TMO", "ABT", "DHR", "PFE", "BMY",
    "AMGN", "MDT", "GILD", "CVS", "CI", "ISRG", "SYK", "WMT", "HD", "PG",
    "COST", "PEP", "KO", "MCD", "NKE", "SBUX", "LOW", "TGT", "MDLZ", "MO",
    "PM", "CL", "XOM", "CVX", "COP", "SLB", "CAT", "BA", "HON", "GE", "UNP",
    "UPS", "RTX", "LMT", "DE", "MMM", "EMR", "FDX", "GD", "NSC", "ITW", "LIN",
    "NEE", "DUK", "SO", "AMT", "PLD", "DIS", "VZ", "T",
)
_SPY = "SPY"


# ---------------------------------------------------------------------------
# Prices (akshare)
# ---------------------------------------------------------------------------


def _normalize_price_frame(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Project an akshare stock_us_daily frame to the unified price schema.

    akshare returns qfq-adjusted OHLC + volume (no separate adj_close), so
    ``adj_close`` is set equal to the qfq ``close``. Non-positive / missing
    close or volume rows are dropped (never fabricated)."""

    import pandas as pd

    out = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["date"]).dt.strftime("%Y-%m-%d"),
            "ticker": ticker,
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "adj_close": pd.to_numeric(raw["close"], errors="coerce"),
            "volume": pd.to_numeric(raw["volume"], errors="coerce"),
        }
    )
    out = out.dropna(subset=["close", "volume"])
    out = out[out["close"] > 0].reset_index(drop=True)
    return out[list(_PRICE_COLUMNS)]


def _fetch_one_price(ticker: str) -> pd.DataFrame:
    """Cached per-ticker qfq price fetch -> normalized unified-schema frame."""

    import pandas as pd

    cache = _BY_TICKER_DIR / f"{ticker}.csv"
    if cache.is_file():
        return pd.read_csv(cache, dtype={"ticker": str})
    import akshare as ak

    frame = _normalize_price_frame(ak.stock_us_daily(symbol=ticker, adjust="qfq"), ticker)
    _BY_TICKER_DIR.mkdir(parents=True, exist_ok=True)
    frame.to_csv(cache, index=False)
    return frame


def fetch_prices() -> tuple[pd.DataFrame, list[str], list[str]]:
    """Fetch all universe tickers + SPY -> (unified_frame, covered, missing)."""

    import pandas as pd

    frames: list[pd.DataFrame] = []
    covered: list[str] = []
    missing: list[str] = []
    for ticker in (*US100, _SPY):
        try:
            frame = _fetch_one_price(ticker)
        except Exception as exc:  # noqa: BLE001 — best-effort per ticker
            missing.append(ticker)
            print(f"  SKIP {ticker}: {type(exc).__name__} {str(exc)[:70]}")
            continue
        if frame.empty:
            missing.append(ticker)
            print(f"  SKIP {ticker}: empty frame")
            continue
        frames.append(frame)
        covered.append(ticker)
        print(f"  OK   {ticker}: {len(frame)} rows ({frame['date'].min()}..{frame['date'].max()})")
    if not frames:
        return pd.DataFrame(columns=list(_PRICE_COLUMNS)), covered, missing
    unified = (
        pd.concat(frames, ignore_index=True)
        .sort_values(["ticker", "date"])
        .reset_index(drop=True)
    )
    return unified, covered, missing


# ---------------------------------------------------------------------------
# Fundamentals (SEC EDGAR companyfacts)
# ---------------------------------------------------------------------------


def _sec_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _SEC_USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310 — fixed SEC host
        return resp.read()


def load_ticker_cik_map() -> dict[str, str]:
    """ticker (upper) -> zero-padded 10-digit CIK, from SEC company_tickers.json."""

    data = json.loads(_sec_get(_SEC_TICKERS_URL))
    out: dict[str, str] = {}
    for entry in data.values():
        out[str(entry["ticker"]).upper()] = str(entry["cik_str"]).zfill(10)
    return out


def _latest_by_end(entries: list[dict], *, annual_only: bool) -> dict[str, tuple[float, str]]:
    """Map period-end -> (value, filed) keeping the latest-filed entry per end date.

    When ``annual_only`` we keep only full-year duration facts (fp == 'FY' and a
    10-K form) — the annual NetIncome. Instant facts (equity, liabilities) pass
    everything through and are deduped by end date."""

    by_end: dict[str, tuple[float, str]] = {}
    for e in entries:
        end = e.get("end")
        filed = e.get("filed")
        val = e.get("val")
        if end is None or filed is None or val is None:
            continue
        if annual_only:
            if e.get("fp") != "FY":
                continue
            if not str(e.get("form", "")).startswith("10-K"):
                continue
        prev = by_end.get(end)
        if prev is None or filed > prev[1]:
            by_end[end] = (float(val), filed)
    return by_end


def extract_annual_fundamentals(companyfacts: dict, ticker: str) -> list[dict]:
    """Extract per-annual-period (period_end, filed, ni, equity, liabilities, roe, dte).

    Pure (no IO) so it is unit-testable. A period is emitted only when both annual
    NetIncome and StockholdersEquity are present for that end date and equity > 0.
    ``filed`` is the LATEST filed date among the joined components — the earliest
    date the whole record was public (used downstream for point-in-time gating)."""

    gaap = companyfacts.get("facts", {}).get("us-gaap", {})

    def usd(tag: str) -> list[dict]:
        return gaap.get(tag, {}).get("units", {}).get("USD", [])

    ni = _latest_by_end(usd("NetIncomeLoss"), annual_only=True)
    eq = _latest_by_end(usd("StockholdersEquity"), annual_only=False)
    liab = _latest_by_end(usd("Liabilities"), annual_only=False)

    records: list[dict] = []
    for end, (ni_val, ni_filed) in ni.items():
        if end not in eq:
            continue
        eq_val, eq_filed = eq[end]
        if eq_val <= 0:
            continue
        liab_val = liab[end][0] if end in liab else None
        liab_filed = liab[end][1] if end in liab else ni_filed
        filed = max(ni_filed, eq_filed, liab_filed)
        records.append(
            {
                "ticker": ticker,
                "period_end": end,
                "filed": filed,
                "net_income": ni_val,
                "equity": eq_val,
                "liabilities": liab_val if liab_val is not None else "",
                "roe": ni_val / eq_val,
                "debt_to_equity": (liab_val / eq_val) if liab_val is not None else "",
            }
        )
    records.sort(key=lambda r: r["period_end"])
    return records


def _fetch_companyfacts(cik: str, ticker: str) -> dict:
    """Cached raw companyfacts JSON fetch."""

    cache = _SEC_RAW_DIR / f"{ticker}.json"
    if cache.is_file():
        return json.loads(cache.read_text())
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    raw = _sec_get(url)
    _SEC_RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(raw)
    time.sleep(0.15)  # be polite to SEC (well under their 10 req/s limit)
    return json.loads(raw)


def fetch_fundamentals(covered_tickers: list[str]) -> tuple[pd.DataFrame, list[str], list[str]]:
    """Fetch SEC annual fundamentals for covered tickers -> (frame, ok, missing)."""

    import pandas as pd

    try:
        cik_map = load_ticker_cik_map()
    except Exception as exc:  # noqa: BLE001
        print(f"  SEC ticker map FAILED: {type(exc).__name__} {str(exc)[:70]}")
        return pd.DataFrame(columns=list(_FUNDAMENTALS_COLUMNS)), [], list(covered_tickers)

    all_records: list[dict] = []
    ok: list[str] = []
    missing: list[str] = []
    for ticker in covered_tickers:
        if ticker == _SPY:
            continue
        cik = cik_map.get(ticker.upper())
        if cik is None:
            missing.append(ticker)
            print(f"  SEC SKIP {ticker}: no CIK")
            continue
        try:
            facts = _fetch_companyfacts(cik, ticker)
            records = extract_annual_fundamentals(facts, ticker)
        except Exception as exc:  # noqa: BLE001
            missing.append(ticker)
            print(f"  SEC SKIP {ticker}: {type(exc).__name__} {str(exc)[:60]}")
            continue
        if not records:
            missing.append(ticker)
            print(f"  SEC SKIP {ticker}: no annual records")
            continue
        all_records.extend(records)
        ok.append(ticker)
        print(f"  SEC OK   {ticker}: {len(records)} annual periods "
              f"({records[0]['period_end']}..{records[-1]['period_end']})")
    frame = pd.DataFrame(all_records, columns=list(_FUNDAMENTALS_COLUMNS))
    return frame, ok, missing


def main() -> int:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Universe: {len(US100)} names + SPY baseline")

    print("\n[1/2] Fetching prices (akshare stock_us_daily qfq) ...")
    prices, covered, missing = fetch_prices()
    prices.to_csv(_UNIFIED_CSV, index=False)
    n_universe = len([t for t in covered if t in US100])
    print(f"wrote {_UNIFIED_CSV}: {len(prices)} rows, "
          f"{n_universe}/{len(US100)} universe + {'SPY' if _SPY in covered else 'no-SPY'}. "
          f"missing={missing}")

    print("\n[2/2] Fetching fundamentals (SEC EDGAR companyfacts) ...")
    fundamentals, sec_ok, sec_missing = fetch_fundamentals(covered)
    fundamentals.to_csv(_FUNDAMENTALS_CSV, index=False)
    print(f"wrote {_FUNDAMENTALS_CSV}: {len(fundamentals)} rows, "
          f"{len(sec_ok)}/{n_universe} tickers with SEC quality data. missing={sec_missing}")

    return 0 if (not prices.empty and _SPY in covered) else 1


if __name__ == "__main__":
    raise SystemExit(main())
