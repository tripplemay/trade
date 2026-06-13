"""B061 F003 — market-aware trading-calendar gap detection.

The data-quality layer flags a "trading calendar gap" when a loaded price
series skips an unexpectedly long stretch. Per path-doc §9.6 the check must not
mistake a non-US market's holidays for missing data.

**Adjudication (B061 F003 — spec premise vs. code reality).** §9.6 assumed a
*daily* trading-day gap check that would false-positive on China's holidays. The
actual check (:func:`trading_calendar_gaps`, extracted here from
``trade/data/loader._calendar_gaps``) is **month-coarse**: it only flags when
two consecutive trading dates are more than one calendar month apart. That
granularity is inherently safe for every market whose longest exchange closure
is well under a month — including China, whose longest A-share closure (Spring
Festival) is ~1 week. So the CN false-gap problem §9.6 warns about **does not
occur**, and no per-market daily holiday calendar is required to avoid it.

Consequently this module does **not** wire a daily CN holiday calendar (which
would need a network source such as akshare's trade-calendar API) into the
offline, deterministic ``trade`` engine — that would over-couple it for zero P1
benefit (``trade`` ingests no CN data in P1; A-share data lives in the workbench
symbol-lookup layer). A precise daily per-market calendar is the right tool only
when *daily* CN gap detection is actually needed (a P2 concern), and it belongs
in the workbench layer where the akshare dependency already lives.

What this module ships: the named calendar home (consumed by the loader), the
canonical market-detection utilities for the ``trade`` layer, and — verified by
the regression test — the guarantee that a normal CN holiday-week gap is **not**
flagged while a genuine multi-month hole still is.

``market_for_symbol`` mirrors workbench's ``SymbolRef`` suffix convention; the
``trade`` package cannot import ``workbench_api`` (the dependency points the
other way), so this is a small standalone copy of that rule.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date
from typing import Literal

Market = Literal["US", "CN"]

# A trailing ``.SH`` / ``.SZ`` marks a China-market canonical symbol; a bare
# ticker is US (matches workbench SymbolRef). Extend when a new market lands.
_CN_SUFFIXES: tuple[str, ...] = (".SH", ".SZ")


def market_for_symbol(symbol: str) -> Market:
    """Market of a canonical symbol: ``.SH`` / ``.SZ`` → ``CN``; bare → ``US``."""
    if symbol.strip().upper().endswith(_CN_SUFFIXES):
        return "CN"
    return "US"


def snapshot_market(symbols: Iterable[str]) -> Market:
    """Market of a whole snapshot: ``CN`` only when **every** symbol is a CN
    code, else ``US``. A mixed / US snapshot keeps ``US`` — which is also correct
    for CN rows given the month-coarse gap granularity (see module docstring)."""
    markets = [market_for_symbol(symbol) for symbol in symbols]
    if markets and all(market == "CN" for market in markets):
        return "CN"
    return "US"


def trading_calendar_gaps(trading_dates: tuple[date, ...]) -> tuple[str, ...]:
    """Flag month-coarse gaps in an ordered trading-date series.

    A gap is recorded when two consecutive trading dates are more than one
    calendar month apart. This granularity is market-agnostic *and* CN-safe:
    no exchange holiday (US or CN) spans more than a month, so only genuine
    multi-month data holes are flagged — never a holiday week.
    """
    gaps: list[str] = []
    for earlier, later in zip(trading_dates, trading_dates[1:], strict=False):
        if _month_index(later) - _month_index(earlier) > 1:
            gaps.append(f"{earlier.isoformat()}..{later.isoformat()}")
    return tuple(gaps)


def _month_index(value: date) -> int:
    return value.year * 12 + value.month
