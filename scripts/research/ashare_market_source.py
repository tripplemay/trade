"""B086 F001 — robust multi-source A-share ETF daily-price fetch layer.

Motivation (direct, from this session): B082–B085 each fetched A-share market data
ad-hoc, and B084 F001 hit an **Eastmoney IP rate-limit** (``SSLError`` to
``push2his.eastmoney.com``) mid-run and had to fall back to Sina by hand to get ETF
prices at all. This module codifies that fallback as a **tested, robust** layer so
every future strategy stops re-hitting the same rate-limit / format traps.

Source order (empirically established this session):
  1. **Eastmoney** ``akshare.fund_etf_hist_em`` (qfq-adjusted) — richest, but rate-limits.
  2. **Sina** ``akshare.fund_etf_hist_sina`` (raw / non-adjusted) — different host, dodges
     the Eastmoney limit; longer history.

The returned frame is annotated with ``source`` and ``adjust`` (``qfq`` vs ``raw``) so a
caller can never silently mix price conventions. A source that raises (SSLError, connection
error, …) or returns empty is skipped with a logged reason; if **all** sources fail the
function raises :class:`DataSourceError` — it never returns empty silently.

Layering (§12.10.2): lives in the **research** layer (with the b084/b085 fetch scripts it
consolidates), NOT ``trade/data/`` — those are pure CSV readers that must not depend on
akshare. Research-safe read-only: touches no strategy, no cn_attack flagship, no production
``data_root``; writes nothing. Completed B082–B085 fetch scripts are left untouched.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_START_DEFAULT = "20180101"
_END_DEFAULT = "20250705"


class DataSourceError(RuntimeError):
    """Raised when every configured market-data source fails for a symbol."""


def sina_symbol(code: str) -> str:
    """Prefix a bare 6-digit ETF code for Sina: ``sh`` for 5xxxxx/6xxxxx (Shanghai),
    ``sz`` for 0/1/3xxxxx (Shenzhen)."""

    if len(code) != 6 or not code.isdigit():
        raise ValueError(f"expected a 6-digit ETF code, got {code!r}")
    return ("sh" if code[0] in "56" else "sz") + code


def _fetch_eastmoney(code: str, start: str, end: str) -> Any:
    """Eastmoney (qfq-adjusted). Normalised to date/ticker/close/source/adjust."""

    import akshare as ak
    import pandas as pd

    df = ak.fund_etf_hist_em(
        symbol=code, period="daily", start_date=start, end_date=end, adjust="qfq"
    )
    if df is None or len(df) == 0:
        return None
    date_col = next(c for c in df.columns if "日期" in c or "date" in c.lower())
    close_col = next(c for c in df.columns if "收盘" in c or c.lower() == "close")
    return pd.DataFrame(
        {
            "date": pd.to_datetime(df[date_col]),
            "ticker": code,
            "close": df[close_col].astype(float),
            "source": "eastmoney",
            "adjust": "qfq",
        }
    )


def _fetch_sina(code: str, start: str, end: str) -> Any:
    """Sina (raw / non-adjusted). Different host — dodges the Eastmoney rate-limit.
    Filtered to [start, end] to match the Eastmoney contract."""

    import akshare as ak
    import pandas as pd

    df = ak.fund_etf_hist_sina(symbol=sina_symbol(code))
    if df is None or len(df) == 0:
        return None
    out = pd.DataFrame(
        {
            "date": pd.to_datetime(df["date"]),
            "ticker": code,
            "close": df["close"].astype(float),
            "source": "sina",
            "adjust": "raw",
        }
    )
    lo, hi = pd.to_datetime(start), pd.to_datetime(end)
    return out[(out["date"] >= lo) & (out["date"] <= hi)].reset_index(drop=True)


# Ordered (name, fetcher). Referenced by global name so tests can monkeypatch either.
def _sources() -> tuple[tuple[str, Any], ...]:
    return (("eastmoney", _fetch_eastmoney), ("sina", _fetch_sina))


def fetch_etf_daily(
    code: str, start: str = _START_DEFAULT, end: str = _END_DEFAULT
) -> Any:
    """Fetch one ETF's daily closes, trying each source in order until one yields rows.

    Returns a DataFrame with columns date/ticker/close/source/adjust (never empty).
    Raises :class:`DataSourceError` if every source fails or returns empty — never a
    silent empty frame (so callers can't mistake a rate-limit for "no data").
    """

    errors: list[str] = []
    for name, fetch in _sources():
        try:
            df = fetch(code, start, end)
        except Exception as exc:  # noqa: BLE001 — any source failure → try the next
            errors.append(f"{name}: {type(exc).__name__}")
            logger.warning("ashare source %s failed for %s: %s", name, code, exc)
            continue
        if df is not None and len(df) > 0:
            if len(errors):
                logger.info("ashare %s served %s after %s", name, code, errors)
            return df
        errors.append(f"{name}: empty")
    raise DataSourceError(f"all sources failed for ETF {code}: {errors}")
