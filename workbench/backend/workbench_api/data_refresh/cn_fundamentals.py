"""B065 F002 — A-share CAS fundamentals → the unified ``fundamentals.csv`` schema.

Maps akshare's CAS (Chinese Accounting Standards) quarterly financials onto the
**exact same** ``FUNDAMENTALS_HEADER`` the SEC EDGAR path writes, so the CN rows
sit beside the US rows in one ``fundamentals.csv`` and the offline
``trade.strategies.us_quality_momentum`` factors (``quality_score`` /
``value_score``, already point-in-time aware via ``report_date <= cutoff``) work
on A-shares with **no strategy change** (spec §1 core insight).

§23 (framework v0.9.45) reachability — verified by real akshare runs:
``stock_financial_abstract(code)`` returns a deep *metric × period* pivot — 600519
came back with **102 historical quarter columns (1998→2026Q1)** carrying
净资产收益率(ROE) / 毛利率 / 资产负债率 / 基本每股收益 / 每股企业自由现金流量 /
每股经营现金流 / 归母净利润 (eastmoney finance host, reachable local + VM). Valuation
(close / PE(TTM) / 市净率) is reused from the F001 ``stock_value_em`` series
(:class:`~workbench_api.data_refresh.cn_universe.MarketCapBar`), so no second
endpoint is needed.

**Point-in-time discipline (mirrors the SEC ``report_date = max(filed)`` rule):**
akshare gives the *period end* (e.g. 20260331), but CAS results are not public
until the CSRC mandatory-disclosure deadline (~1 month after quarter end, the
annual by next-April-30). Using the raw period end as ``report_date`` would give
the A-share factor a lookahead the US factor doesn't have, so
:func:`cas_disclosure_date` maps each period end to its **conservative disclosure
deadline** — the strategy then "knows" a quarter only once it was guaranteed
public.

**Unit / 口径 honesty (spec §3 F002 "CAS 口径诚实标注"):** akshare emits ROE /
margins / debt ratio as **percent** → stored as the SEC-matching **fraction**
(÷100). ``debt_to_assets`` is CAS 资产负债率 = *total liabilities / total assets*,
whereas the SEC column is *long-term debt / assets* — a different numerator. Both
are leverage measures and the quality factor only percent-ranks within a
cross-section (the A-share strategy ranks A-shares against A-shares), so the
scale is internally consistent; the numerator difference is documented here.
``ev_ebitda`` is left null (CAS abstract has no clean EV/EBITDA) — the value
factor skips NaN components.

akshare lives only in this workbench job (the loader is injected / lazy); this
module imports neither ``trade`` nor a broker SDK.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Sequence
from datetime import date
from typing import Any

from workbench_api.data_refresh.cn_marketcap import CnMarketCapLoader
from workbench_api.data_refresh.cn_universe import MarketCapBar
from workbench_api.symbols.akshare_frames import coerce_date, coerce_float, frame_records
from workbench_api.symbols.symbol_ref import SymbolRef

logger = logging.getLogger(__name__)

# CAS stock_financial_abstract 指标 names (rows; periods are YYYYMMDD columns).
_IND_ROE = "净资产收益率(ROE)"
_IND_GROSS_MARGIN = "毛利率"
_IND_DEBT_ASSET = "资产负债率"
_IND_EPS = "基本每股收益"
_IND_FCF_PS = "每股企业自由现金流量"  # FCF per share (NaN in some interim quarters)
_IND_CFO_PS = "每股经营现金流"  # CFO per share — fcf_yield fallback (capex≈0, SEC-style)

# Disclosure deadlines (CSRC): the conservative public-by date per period end.
# (month, day) of period end -> (month, day, year_offset) of the deadline.
_DISCLOSURE_DEADLINE: dict[tuple[int, int], tuple[int, int, int]] = {
    (3, 31): (4, 30, 0),  # Q1 by Apr 30
    (6, 30): (8, 31, 0),  # Semi by Aug 31
    (9, 30): (10, 31, 0),  # Q3 by Oct 31
    (12, 31): (4, 30, 1),  # Annual by next Apr 30
}
_FALLBACK_LAG_DAYS = 90  # non-standard period ends: conservative ~quarter lag


def cas_disclosure_date(period_end: date) -> date:
    """Conservative public-availability date for a CAS period (no lookahead)."""

    deadline = _DISCLOSURE_DEADLINE.get((period_end.month, period_end.day))
    if deadline is None:
        from datetime import timedelta

        return period_end + timedelta(days=_FALLBACK_LAG_DAYS)
    month, day, year_offset = deadline
    return date(period_end.year + year_offset, month, day)


def fiscal_quarter_label(period_end: date) -> str:
    """Period end -> ``"YYYYQn"`` (calendar quarter of the period end)."""

    quarter = (period_end.month - 1) // 3 + 1
    return f"{period_end.year}Q{quarter}"


def _period_ends(columns: Sequence[str]) -> list[date]:
    """Parsed ``YYYYMMDD`` report-period columns, oldest first."""

    out: list[date] = []
    for col in columns:
        text = str(col)
        if len(text) == 8 and text.isdigit():
            parsed = coerce_date(text)
            if parsed is not None:
                out.append(parsed)
    return sorted(out)


def _nearest_bar(bars: Sequence[MarketCapBar], target: date) -> MarketCapBar | None:
    """The valuation bar closest in time to ``target`` (for ratios at disclosure)."""

    if not bars:
        return None
    return min(bars, key=lambda bar: abs((bar.bar_date - target).days))


def _frac(value: float | None) -> float | None:
    return None if value is None else value / 100.0


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def cn_fundamentals_rows(
    ticker: str,
    abstract_records: Sequence[dict[str, Any]],
    abstract_columns: Sequence[str],
    valuation_bars: Sequence[MarketCapBar],
    *,
    from_date: date,
    to_date: date,
) -> tuple[list[dict[str, Any]], list[str]]:
    """CAS ``stock_financial_abstract`` frame → unified ``FUNDAMENTALS_HEADER`` rows.

    One row per reporting period whose end is within ``[from_date, to_date]``,
    keyed exactly like the SEC rows. ``report_date`` is the conservative CAS
    disclosure date (point-in-time). Ratios are best-effort: a metric akshare
    didn't report becomes ``None`` (an empty CSV cell → NaN → the factor skips
    it). Returns ``(rows, skip_messages)``."""

    skips: list[str] = []
    # 指标 -> its record (period_col -> value), first occurrence wins.
    by_indicator: dict[str, dict[str, Any]] = {}
    for record in abstract_records:
        indicator = str(record.get("指标", ""))
        if indicator and indicator not in by_indicator:
            by_indicator[indicator] = record

    def metric(indicator: str, period_col: str) -> float | None:
        row = by_indicator.get(indicator)
        return coerce_float(row.get(period_col)) if row is not None else None

    rows: list[dict[str, Any]] = []
    for period_end in _period_ends(abstract_columns):
        if not (from_date <= period_end <= to_date):
            continue
        period_col = period_end.strftime("%Y%m%d")
        report_date = cas_disclosure_date(period_end)
        bar = _nearest_bar(valuation_bars, report_date)
        close = bar.close if bar is not None else None

        fcf_ps = metric(_IND_FCF_PS, period_col)
        if fcf_ps is None:  # FCF/share NaN in some interim quarters → CFO/share
            fcf_ps = metric(_IND_CFO_PS, period_col)

        roe = _frac(metric(_IND_ROE, period_col))
        gross_margin = _frac(metric(_IND_GROSS_MARGIN, period_col))
        debt_to_assets = _frac(metric(_IND_DEBT_ASSET, period_col))
        if roe is None and gross_margin is None and debt_to_assets is None:
            skips.append(f"{ticker} {period_col}: no CAS quality metrics")
            continue

        rows.append(
            {
                "report_date": report_date.isoformat(),
                "ticker": ticker,
                "fiscal_quarter": fiscal_quarter_label(period_end),
                "fiscal_quarter_end": period_end.isoformat(),
                "roe": _round(roe, 4),
                "gross_margin": _round(gross_margin, 4),
                "fcf_yield": _round(_safe_div(fcf_ps, close), 4),
                "debt_to_assets": _round(debt_to_assets, 4),
                "pe": _round(bar.pe_ttm if bar is not None else None, 2),
                "pb": _round(bar.pb if bar is not None else None, 2),
                "ev_ebitda": None,  # CAS abstract has no clean EV/EBITDA (honest null)
                "earnings_yield": _round(_safe_div(metric(_IND_EPS, period_col), close), 4),
            }
        )
    return rows, skips


def _round(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


class CnFundamentalsLoader:
    """akshare CAS fundamentals → unified ``fundamentals.csv`` rows for one ticker.

    Composes ``stock_financial_abstract`` (CAS metrics, lazy akshare) with the
    F001 :class:`CnMarketCapLoader` (``stock_value_em`` close / PE / PB at the
    disclosure dates). A fetch failure degrades to ``[]`` (the refresh counts it
    best-effort), never a 500."""

    def __init__(
        self,
        akshare_module: Any | None = None,
        marketcap_loader: CnMarketCapLoader | None = None,
    ) -> None:
        self._akshare = akshare_module
        self._marketcap = marketcap_loader or CnMarketCapLoader(akshare_module)

    def _load_akshare(self) -> Any | None:
        if self._akshare is not None:
            return self._akshare
        try:
            return importlib.import_module("akshare")
        except Exception:
            return None

    def fetch_fundamentals_rows(
        self, ticker: str, from_date: date, to_date: date
    ) -> list[dict[str, Any]]:
        akshare = self._load_akshare()
        if akshare is None:
            return []
        code = SymbolRef.parse(ticker).code
        records, columns = frame_records(akshare, "stock_financial_abstract", symbol=code)
        if not records:
            return []
        bars = self._marketcap.fetch_market_cap_history(ticker, from_date, to_date)
        rows, skips = cn_fundamentals_rows(
            ticker, records, columns, bars, from_date=from_date, to_date=to_date
        )
        if skips:
            logger.info("cn_fundamentals_skips", extra={"ticker": ticker, "skips": skips[:5]})
        return rows
