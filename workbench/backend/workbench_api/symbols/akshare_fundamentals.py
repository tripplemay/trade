"""B064 F001 — akshare fundamentals frame → normalized facts (pure, testable).

The CN / HK fundamentals providers fetch akshare frames whose shapes and units
differ from yfinance's ``.info`` and from each other:

* **CN** ``stock_financial_abstract`` is a *metric × period* pivot (选项/指标 +
  one column per ``YYYYMMDD`` report period) carrying revenue / net profit /
  ROE / margins / EPS / BPS / debt ratios — and ``stock_value_em`` is a *daily*
  table carrying 总市值 / PE(TTM) / 市净率 / 总股本 (raw 元 / shares).
* **HK** ``stock_financial_hk_analysis_indicator_em`` is a *period* table with
  English keys (OPERATE_INCOME / HOLDER_PROFIT / BPS / ROE_AVG / … , CURRENCY)
  — and ``stock_hk_valuation_baidu`` is a ``date,value`` series per indicator
  (总市值 in **亿** HKD, 市盈率(TTM), 市净率).

This module centralises the (选项, 指标) / column lookups + the **unit
normalisation** so the providers stay thin and the mapping is unit-tested
without a network. Unit conventions match yfinance so the existing detail-page
formatter is reused unchanged (B064 §3):

* margins / ROE: akshare emits **percent** (e.g. ROE ``24.28``) → stored as the
  **fraction** ``0.2428`` (yfinance ``profitMargins`` / ``returnOnEquity``);
* ``debt_to_equity`` / ``debt_to_asset``: kept in **percent** (yfinance
  ``debtToEquity`` is a percent-magnitude number, e.g. ``145.0``);
* ``market_cap`` / ``revenue`` / ``net_income`` / ``shares_outstanding``: **raw
  currency units** (CN 元 from ``stock_value_em``, HK = baidu 亿 × 1e8).

request-path safe: stdlib + akshare_frames helpers only — no akshare / trade /
broker import at module scope (akshare is lazy-imported inside the providers).
The output is a ``dict`` of :class:`ProviderStats` field names → values that the
provider feeds into ``dataclasses.replace``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from workbench_api.symbols.akshare_frames import coerce_date, coerce_float

# --- CN stock_financial_abstract: (选项, 指标) keys we surface -------------- #
# Exact (选项, 指标) pairs disambiguate metrics that repeat across 选项 groups
# (e.g. 净资产收益率(ROE) appears under both 常用指标 and 盈利能力). A fallback
# searches any 选项 for the 指标 if the preferred pair is absent (akshare may
# relabel a 选项 group).
_CN_REVENUE = ("常用指标", "营业总收入")
_CN_NET_INCOME = ("常用指标", "归母净利润")
_CN_ROE = ("常用指标", "净资产收益率(ROE)")
_CN_GROSS_MARGIN = ("常用指标", "毛利率")
_CN_NET_MARGIN = ("常用指标", "销售净利率")
_CN_DEBT_ASSET = ("常用指标", "资产负债率")
_CN_EPS = ("常用指标", "基本每股收益")
_CN_BVPS = ("常用指标", "每股净资产")
_CN_DEBT_EQUITY = ("财务风险", "产权比率")


def _pct_to_fraction(value: float | None) -> float | None:
    """akshare percent (24.28) → yfinance fraction (0.2428)."""
    return None if value is None else value / 100.0


def _period_columns(columns: list[str]) -> list[tuple[date, str]]:
    """The ``YYYYMMDD`` report-period columns of stock_financial_abstract,
    paired with their parsed date, newest first."""
    periods: list[tuple[date, str]] = []
    for col in columns:
        if len(col) == 8 and col.isdigit():
            parsed = coerce_date(col)
            if parsed is not None:
                periods.append((parsed, col))
    periods.sort(key=lambda pair: pair[0], reverse=True)
    return periods


def cn_fundamentals_facts(
    *,
    abstract_records: list[dict[str, Any]],
    abstract_columns: list[str],
    value_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Normalise the two CN akshare frames into ProviderStats kwargs.

    ``abstract_*`` come from ``stock_financial_abstract`` (statement metrics +
    ratios, CAS); ``value_records`` from ``stock_value_em`` (valuation: 总市值 /
    PE(TTM) / 市净率 / 总股本). Either may be empty — facts are best-effort and
    partial; the service degrades honestly when nothing is found.
    """

    facts: dict[str, Any] = {}

    periods = _period_columns(abstract_columns)
    if abstract_records and periods:
        as_of, latest_col = periods[0]
        # (选项, 指标) → latest-period value + a 指标-only fallback map.
        by_pair: dict[tuple[str, str], float | None] = {}
        by_indicator: dict[str, float | None] = {}
        for row in abstract_records:
            group = str(row.get("选项", ""))
            metric = str(row.get("指标", ""))
            val = coerce_float(row.get(latest_col))
            by_pair[(group, metric)] = val
            by_indicator.setdefault(metric, val)

        def pick(pair: tuple[str, str]) -> float | None:
            if pair in by_pair:
                return by_pair[pair]
            return by_indicator.get(pair[1])

        facts["as_of_report"] = as_of
        facts["revenue"] = pick(_CN_REVENUE)
        facts["net_income"] = pick(_CN_NET_INCOME)
        facts["return_on_equity"] = _pct_to_fraction(pick(_CN_ROE))
        facts["gross_margins"] = _pct_to_fraction(pick(_CN_GROSS_MARGIN))
        facts["profit_margins"] = _pct_to_fraction(pick(_CN_NET_MARGIN))
        facts["debt_to_asset"] = pick(_CN_DEBT_ASSET)
        facts["debt_to_equity"] = pick(_CN_DEBT_EQUITY)
        facts["eps"] = pick(_CN_EPS)
        facts["book_value_per_share"] = pick(_CN_BVPS)

    latest_value = _latest_by_key(value_records, "数据日期")
    if latest_value is not None:
        facts["market_cap"] = coerce_float(latest_value.get("总市值"))
        facts["trailing_pe"] = coerce_float(latest_value.get("PE(TTM)"))
        facts["price_to_book"] = coerce_float(latest_value.get("市净率"))
        facts["shares_outstanding"] = coerce_float(latest_value.get("总股本"))

    return {key: val for key, val in facts.items() if val is not None}


def hk_fundamentals_facts(
    *,
    indicator_records: list[dict[str, Any]],
    market_cap_yi: float | None,
    trailing_pe: float | None,
    price_to_book: float | None,
) -> dict[str, Any]:
    """Normalise the HK akshare frames into ProviderStats kwargs.

    ``indicator_records`` come from ``stock_financial_hk_analysis_indicator_em``
    (annual statement metrics + ratios, HKFRS, English keys); the valuation
    scalars come from ``stock_hk_valuation_baidu`` — ``market_cap_yi`` is in
    **亿** HKD and is scaled to raw HKD here.
    """

    facts: dict[str, Any] = {}

    latest = _latest_by_key(indicator_records, "REPORT_DATE")
    if latest is not None:
        name = latest.get("SECURITY_NAME_ABBR")
        if name:
            facts["long_name"] = str(name)
        currency = latest.get("CURRENCY")
        if currency:
            facts["currency"] = str(currency)
        facts["as_of_report"] = coerce_date(latest.get("REPORT_DATE"))
        facts["revenue"] = coerce_float(latest.get("OPERATE_INCOME"))
        facts["net_income"] = coerce_float(latest.get("HOLDER_PROFIT"))
        facts["eps"] = coerce_float(latest.get("BASIC_EPS"))
        facts["book_value_per_share"] = coerce_float(latest.get("BPS"))
        facts["gross_margins"] = _pct_to_fraction(
            coerce_float(latest.get("GROSS_PROFIT_RATIO"))
        )
        facts["profit_margins"] = _pct_to_fraction(
            coerce_float(latest.get("NET_PROFIT_RATIO"))
        )
        facts["return_on_equity"] = _pct_to_fraction(coerce_float(latest.get("ROE_AVG")))
        facts["debt_to_asset"] = coerce_float(latest.get("DEBT_ASSET_RATIO"))

    if market_cap_yi is not None:
        # baidu 总市值 is in 亿 (1e8) HKD → raw HKD to match yfinance marketCap.
        facts["market_cap"] = market_cap_yi * 1e8
    if trailing_pe is not None:
        facts["trailing_pe"] = trailing_pe
    if price_to_book is not None:
        facts["price_to_book"] = price_to_book

    return {key: val for key, val in facts.items() if val is not None}


def baidu_latest_value(records: list[dict[str, Any]]) -> float | None:
    """The newest ``value`` from a ``stock_*_valuation_baidu`` ``(date, value)``
    frame (one indicator per call: 总市值 / 市盈率(TTM) / 市净率)."""
    latest = _latest_by_key(records, "date")
    return None if latest is None else coerce_float(latest.get("value"))


def _latest_by_key(
    records: list[dict[str, Any]], date_key: str
) -> dict[str, Any] | None:
    """The record with the maximum parseable date under ``date_key`` (akshare
    frames are not reliably sorted; pick the newest explicitly)."""
    best: dict[str, Any] | None = None
    best_date: date | None = None
    for row in records:
        parsed = coerce_date(row.get(date_key))
        if parsed is None:
            continue
        if best_date is None or parsed > best_date:
            best_date, best = parsed, row
    return best
