"""B045 F004 (fix #1) — live SEC companyfacts → unified fundamentals synthesis.

The logic here was the heart of the B029 F002 backfill driver
(``scripts/backfill_fundamentals.py``). It is hoisted into ``workbench_api``
(the deploy artifact) so the on-VM ``data-refresh`` job can produce **real**
fundamentals from live SEC EDGAR companyfacts — ``scripts/`` is a repo-root dev
tree that is NOT shipped to the VM, so the refresh job could never reach this
code while it lived there (B045 F004 Finding #1: ``fundamentals.csv`` 0 rows →
us_quality stub → ``data_source=mixed`` never reaching ``real``).

:func:`raw_companyfacts_to_parsed_ratios` converts a raw SEC companyfacts
payload (the shape :meth:`SECEDGARFundamentalsLoader.fetch_raw_companyfacts`
returns) into rows in the **exact** unified fundamentals CSV schema
(``report_date / ticker / fiscal_quarter / fiscal_quarter_end`` + the eight
ratios). The eight ratio computations reuse
:mod:`workbench_api.data.xbrl_parser` (already deployable).

``scripts/backfill_fundamentals.py`` and ``scripts/universe_us_quality.py`` now
re-import the sector map + synthesis from here (single source of truth; no
duplicated logic between the offline backfill and the on-VM refresh).
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from workbench_api.data.xbrl_parser import (
    SEC_CONCEPT_NAMES,
    compute_debt_to_assets,
    compute_earnings_yield,
    compute_ebitda,
    compute_ev_ebitda,
    compute_fcf_yield,
    compute_gross_margin,
    compute_pb,
    compute_pe,
    compute_roe,
    get_concept_alias_chain,
)

# SEC reports CommonStockSharesOutstanding under the ``dei`` namespace,
# not ``us-gaap``. We special-case that one.
DEI_NAMESPACE = "dei"
USGAAP_NAMESPACE = "us-gaap"

# Shares-outstanding alias chain — multi-namespace because SEC filers drift
# across ``dei``/``us-gaap`` for this concept more than for balance-sheet
# items. The synthesis iterates this list in order and unions every entry,
# then bucketing keeps latest-filed per quarter.
SHARES_OUTSTANDING_ALIASES: tuple[tuple[str, str], ...] = (
    ("dei", "EntityCommonStockSharesOutstanding"),
    ("dei", "CommonStockSharesOutstanding"),
    ("us-gaap", "CommonStockSharesOutstanding"),
    ("us-gaap", "WeightedAverageNumberOfSharesOutstandingBasic"),
)

# B030 F001 — GICS sector per ticker, mirrors the ``gics_sector`` column of
# ``data/fixtures/us_quality_momentum/universe.csv``. The sector front-loads
# the sector-idiomatic SEC concepts through
# :func:`xbrl_parser.get_concept_alias_chain` (Financials / Utilities / Real
# Estate overrides). ``scripts/universe_us_quality.py`` re-exports this map and
# asserts it against the fixture's ``gics_sector`` column (drift → CI fail).
US_QUALITY_TICKER_SECTORS: dict[str, str] = {
    "AAPL": "Information Technology",
    "MSFT": "Information Technology",
    "NVDA": "Information Technology",
    "JNJ": "Health Care",
    "UNH": "Health Care",
    "JPM": "Financials",
    "BAC": "Financials",
    "V": "Financials",
    "AMZN": "Consumer Discretionary",
    "HD": "Consumer Discretionary",
    "GOOGL": "Communication Services",
    "META": "Communication Services",
    "HON": "Industrials",
    "UPS": "Industrials",
    "CAT": "Industrials",
    "PG": "Consumer Staples",
    "KO": "Consumer Staples",
    "WMT": "Consumer Staples",
    "XOM": "Energy",
    "CVX": "Energy",
    "NEE": "Utilities",
    "DUK": "Utilities",
    "PLD": "Real Estate",
    "AMT": "Real Estate",
    "LIN": "Materials",
    "APD": "Materials",
    "ECL": "Materials",
    # Synthetic tickers are skipped in the SEC backfill but kept here so
    # get_ticker_sector returns the B025 fixture value for non-backfill paths.
    "ZQAI": "Industrials",
    "ZQPT": "Information Technology",
    "ZQLH": "Health Care",
}


def get_ticker_sector(ticker: str) -> str | None:
    """Return the GICS sector for ``ticker``, or ``None`` if not in the
    B025 us_quality universe.

    ``None`` (rather than raising) matches the loose-coupling the alias resolver
    expects — callers pass it straight through to
    :func:`xbrl_parser.get_concept_alias_chain`, which falls back to the default
    concept chain on an unrecognised sector.
    """

    return US_QUALITY_TICKER_SECTORS.get(ticker)


def _calendar_quarter(end_date: date) -> tuple[int, int]:
    """Bucket a calendar date into ``(year, quarter_number)``.

    SEC ``end`` dates may be ±1-15 days off a strict quarter-end; the bucketing
    snaps to the nearest calendar quarter without treating the variance as a
    defect.
    """

    return (end_date.year, (end_date.month - 1) // 3 + 1)


def _quarter_end(year: int, q: int) -> date:
    """Return the canonical calendar quarter-end date for ``(year, q)``."""

    return {
        1: date(year, 3, 31),
        2: date(year, 6, 30),
        3: date(year, 9, 30),
        4: date(year, 12, 31),
    }[q]


def _index_concept_entries(
    facts: dict[str, Any],
    concept_name: str,
    namespace: str = USGAAP_NAMESPACE,
) -> list[dict[str, Any]]:
    """Pull the unit entries for ``concept_name`` from the SEC companyfacts
    ``facts`` sub-tree (namespace-aware so ``dei`` concepts resolve too)."""

    ns_facts = facts.get(namespace, {})
    if not isinstance(ns_facts, dict):
        return []
    concept = ns_facts.get(concept_name, {})
    if not isinstance(concept, dict):
        return []
    units = concept.get("units", {})
    if not isinstance(units, dict):
        return []
    # USD covers monetary concepts; "shares" covers SharesOutstanding.
    for unit_key in ("USD", "shares", "USD/shares"):
        entries = units.get(unit_key)
        if isinstance(entries, list):
            return [e for e in entries if isinstance(e, dict)]
    return []


def _bucket_entries_by_quarter(
    entries: list[dict[str, Any]],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Bucket concept entries by calendar quarter, keeping the latest-filed
    entry whose ``end`` date falls in that quarter (10-K/A and 10-Q
    restatements: latest-filed wins)."""

    out: dict[tuple[int, int], dict[str, Any]] = {}
    for entry in entries:
        try:
            end_dt = date.fromisoformat(str(entry["end"]))
        except (KeyError, ValueError):
            continue
        if "filed" not in entry or "val" not in entry:
            continue
        bucket = _calendar_quarter(end_dt)
        prev = out.get(bucket)
        if prev is None or str(entry["filed"]) > str(prev["filed"]):
            out[bucket] = entry
    return out


def _derive_shares_from_dividends(
    facts: dict[str, Any],
    existing: dict[tuple[int, int], dict[str, Any]],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Synthesise ``shares_outstanding`` from dividends when SEC doesn't file
    the concept directly (B030 F004 fix-round 1).

    Visa is the canonical case: it stops filing
    ``EntityCommonStockSharesOutstanding`` quarterly and never files
    ``WeightedAverageNumberOfSharesOutstandingBasic``, but DOES file
    ``DividendsCommonStockCash`` + ``CommonStockDividendsPerShareCashPaid``.
    ``total / per_share`` is the share count receiving the dividend — exactly
    what MarketCap needs. Only fills quarters where shares is NOT already filed.
    """

    div_total = _bucket_entries_by_quarter(
        _index_concept_entries(facts, "DividendsCommonStockCash", "us-gaap"),
    )
    div_per_share = _bucket_entries_by_quarter(
        _index_concept_entries(facts, "CommonStockDividendsPerShareCashPaid", "us-gaap"),
    )
    out: dict[tuple[int, int], dict[str, Any]] = dict(existing)
    for key in div_total.keys() & div_per_share.keys():
        if key in out:
            continue
        total_entry = div_total[key]
        per_share_entry = div_per_share[key]
        try:
            total_val = float(total_entry["val"])
            per_share_val = float(per_share_entry["val"])
        except (KeyError, TypeError, ValueError):
            continue
        if per_share_val <= 0 or total_val <= 0:
            continue
        derived = total_val / per_share_val
        out[key] = {
            "end": per_share_entry.get("end", total_entry.get("end")),
            "val": derived,
            "filed": per_share_entry.get("filed", total_entry.get("filed")),
            "fy": per_share_entry.get("fy"),
            "fp": per_share_entry.get("fp"),
            "form": per_share_entry.get("form"),
            "accn": per_share_entry.get("accn"),
            "_b030_derived_from": "DividendsCommonStockCash/CommonStockDividendsPerShareCashPaid",
        }
    return out


def _propagate_annual_shares_to_quarterly(
    bucketed: dict[tuple[int, int], dict[str, Any]],
    candidate_quarters: set[tuple[int, int]],
) -> dict[tuple[int, int], dict[str, Any]]:
    """Fill quarterly shares-outstanding buckets from an adjacent annual entry
    (B030 F004 fix-round 1).

    Some filers (Visa) report ``EntityCommonStockSharesOutstanding`` only on the
    annual 10-K cover page. This copies that value into Q1-Q3 of the same fiscal
    year — but ONLY for quarters that already appear in OTHER concept buckets
    (no fictitious quarters). The approximation (shares ≈ constant within a
    fiscal year) holds to sub-percent for the canonical names. Returns a NEW dict.
    """

    if not bucketed or not candidate_quarters:
        return dict(bucketed)
    out: dict[tuple[int, int], dict[str, Any]] = dict(bucketed)
    for year, q in candidate_quarters:
        if (year, q) in out:
            continue
        anchor = (
            bucketed.get((year, 4))
            or bucketed.get((year, 3))
            or bucketed.get((year, 2))
            or bucketed.get((year, 1))
            or bucketed.get((year - 1, 4))
        )
        if anchor is not None:
            out[(year, q)] = anchor
    return out


def load_close_prices(prices_csv: Path) -> dict[tuple[str, str], float]:
    """Index a unified prices CSV by ``(ticker, date-iso)`` → close.

    Returns an empty dict if the file doesn't exist (caller skips the
    MarketCap-dependent ratios on missing prices).
    """

    if not prices_csv.exists():
        return {}
    out: dict[tuple[str, str], float] = {}
    with prices_csv.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                out[(row["ticker"], row["date"])] = float(row["close"])
            except (KeyError, ValueError):
                continue
    return out


def _nearest_close(
    prices: dict[tuple[str, str], float],
    ticker: str,
    target: date,
    *,
    max_offset_days: int = 5,
) -> float | None:
    """Close for ``ticker`` on ``target`` (or up to ``max_offset_days`` back for
    weekends / holidays). Returns ``None`` if no price is found."""

    for offset in range(max_offset_days + 1):
        probe = target - timedelta(days=offset)
        close = prices.get((ticker, probe.isoformat()))
        if close is not None:
            return close
    return None


def raw_companyfacts_to_parsed_ratios(
    ticker: str,
    payload: dict[str, Any],
    *,
    prices: dict[tuple[str, str], float],
    sector: str | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Convert raw SEC companyfacts JSON into unified-fundamentals rows.

    Returns ``(rows, skip_messages)``. Each row is a dict in the 12-column
    unified fundamentals schema (``report_date / ticker / fiscal_quarter /
    fiscal_quarter_end`` + the eight ratios). ``skip_messages`` carries a
    human-readable reason per quarter dropped (missing concept / no price
    intersection / zero denominator).

    ``sector`` front-loads per-sector concept aliases (Financials / Utilities /
    Real Estate) via :func:`xbrl_parser.get_concept_alias_chain`; ``None`` or an
    unrecognised sector falls through to the default concept chain.
    """

    facts = payload.get("facts", {})
    if not isinstance(facts, dict):
        return [], [f"{ticker}: companyfacts missing 'facts' object"]

    indexed: dict[str, dict[tuple[int, int], dict[str, Any]]] = {}
    for short_name in SEC_CONCEPT_NAMES:
        concept_aliases = get_concept_alias_chain(ticker, short_name, sector)
        combined: list[dict[str, Any]] = []
        for concept_name in concept_aliases:
            combined.extend(_index_concept_entries(facts, concept_name, USGAAP_NAMESPACE))
        indexed[short_name] = _bucket_entries_by_quarter(combined)
    shares_entries: list[dict[str, Any]] = []
    for ns, concept_name in SHARES_OUTSTANDING_ALIASES:
        shares_entries.extend(_index_concept_entries(facts, concept_name, ns))
    indexed["shares_outstanding"] = _bucket_entries_by_quarter(shares_entries)
    indexed["shares_outstanding"] = _derive_shares_from_dividends(
        facts, indexed["shares_outstanding"]
    )

    all_quarters: set[tuple[int, int]] = set()
    for bucket in indexed.values():
        all_quarters |= set(bucket.keys())
    indexed["shares_outstanding"] = _propagate_annual_shares_to_quarterly(
        indexed["shares_outstanding"], all_quarters
    )

    rows: list[dict[str, Any]] = []
    skip_messages: list[str] = []
    # Banks (Financials) structurally don't file traditional capex; treat
    # missing capex as 0 so fcf_yield = CFO / MarketCap. Other sectors require it.
    capex_optional = sector == "Financials"
    required_short_names = (
        "net_income",
        "stockholders_equity",
        "revenues",
        "cogs",
        "cfo",
        "long_term_debt",
        "assets",
        "cash",
        "operating_income",
        "depreciation_amortization",
        "shares_outstanding",
    ) + (() if capex_optional else ("capex",))
    for year, q in sorted(all_quarters):
        fiscal_quarter = f"{year}Q{q}"
        missing = [sn for sn in required_short_names if (year, q) not in indexed.get(sn, {})]
        if missing:
            skip_messages.append(f"{ticker} {fiscal_quarter}: missing concepts {missing}")
            continue
        try:
            net_income = float(indexed["net_income"][(year, q)]["val"])
            se = float(indexed["stockholders_equity"][(year, q)]["val"])
            revenues = float(indexed["revenues"][(year, q)]["val"])
            cogs = float(indexed["cogs"][(year, q)]["val"])
            cfo = float(indexed["cfo"][(year, q)]["val"])
            if capex_optional and (year, q) not in indexed["capex"]:
                capex = 0.0
            else:
                capex = abs(float(indexed["capex"][(year, q)]["val"]))
            long_term_debt = float(indexed["long_term_debt"][(year, q)]["val"])
            assets = float(indexed["assets"][(year, q)]["val"])
            cash = float(indexed["cash"][(year, q)]["val"])
            operating_income = float(indexed["operating_income"][(year, q)]["val"])
            d_and_a = float(indexed["depreciation_amortization"][(year, q)]["val"])
            shares = float(indexed["shares_outstanding"][(year, q)]["val"])
        except (KeyError, TypeError, ValueError) as exc:
            skip_messages.append(f"{ticker} {fiscal_quarter}: concept value cast failed ({exc})")
            continue

        filed_dates = []
        for sn in required_short_names:
            entry = indexed[sn].get((year, q))
            if entry and "filed" in entry:
                filed_dates.append(str(entry["filed"]))
        if not filed_dates:
            skip_messages.append(f"{ticker} {fiscal_quarter}: no filed date on any concept")
            continue
        report_date = max(filed_dates)
        report_dt = date.fromisoformat(report_date)
        fq_end_str = str(indexed["assets"][(year, q)]["end"])
        try:
            fq_end_dt = date.fromisoformat(fq_end_str)
        except ValueError:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: bad fiscal_quarter_end '{fq_end_str}'"
            )
            continue

        close = _nearest_close(prices, ticker, report_dt)
        if close is None:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: no Tiingo close near "
                f"report_date {report_date} (±5d)"
            )
            continue
        market_cap = close * shares
        if market_cap <= 0:
            skip_messages.append(
                f"{ticker} {fiscal_quarter}: market_cap non-positive "
                f"(close={close} × shares={shares})"
            )
            continue

        net_income_ttm = net_income
        ebitda = compute_ebitda(operating_income, d_and_a)
        try:
            roe = compute_roe(net_income, se)
            gross_margin = compute_gross_margin(revenues, cogs)
            fcf_yield = compute_fcf_yield(cfo, capex, market_cap)
            debt_to_assets = compute_debt_to_assets(long_term_debt, assets)
            pe = compute_pe(market_cap, net_income_ttm)
            pb = compute_pb(market_cap, se)
            ev_ebitda = compute_ev_ebitda(market_cap, long_term_debt, cash, ebitda)
            earnings_yield = compute_earnings_yield(net_income_ttm, market_cap)
        except ValueError as exc:
            skip_messages.append(f"{ticker} {fiscal_quarter}: ratio compute failed ({exc})")
            continue

        rows.append(
            {
                "report_date": report_date,
                "ticker": ticker,
                "fiscal_quarter": fiscal_quarter,
                "fiscal_quarter_end": fq_end_dt.isoformat(),
                "roe": round(roe, 4),
                "gross_margin": round(gross_margin, 4),
                "fcf_yield": round(fcf_yield, 4),
                "debt_to_assets": round(debt_to_assets, 4),
                "pe": round(pe, 2),
                "pb": round(pb, 2),
                "ev_ebitda": round(ev_ebitda, 2),
                "earnings_yield": round(earnings_yield, 4),
            }
        )
    return rows, skip_messages
