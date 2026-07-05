"""B091 F001 — regression tests for the cross-calendar ``above_200d_ma`` bug.

The bug (B090 §6, Codex-confirmed): ``above_200d_ma`` rolled the 200D MA over
``_wide_close``'s UNION frame. When the universe spans multiple trading calendars
(HK + mainland-A + US), cross-market-only dates inject NaNs into each ticker's
column, so no ticker ever accumulates ``ma_long`` non-NaN values inside a
``ma_long``-ROW window → ``min_periods=200`` never fills → MA is permanently NaN
→ every ticker reads "below MA" → ``regional_risk_off`` fires every quarter and
the individual-stock sleeve sits 100% in cash.

The fix computes each ticker's MA on its OWN calendar (per-column dropna before
the rolling window). These tests pin:

* (a) MULTI-CALENDAR FIX — a genuinely uptrending ticker on a sparse calendar
  now resolves ``above_MA=True`` (was ``False`` under the bug).
* (b) ZERO-REGRESSION NO-OP — on a single-calendar (gap-free) frame the fixed
  output equals the OLD union-frame computation byte-for-byte (the live
  ETF-proxy path is unchanged).
* (c) INSUFFICIENT HISTORY — a ticker with < ``ma_long`` own observations still
  resolves ``False``.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trade.strategies.hk_china_momentum.factors import (
    _wide_close,
    above_200d_ma,
)

_AS_OF = date(2024, 6, 28)
_MA_LONG = 200


def _rows(
    ticker: str, closes: dict[date, float]
) -> list[dict[str, object]]:
    return [
        {"date": d.isoformat(), "ticker": ticker, "adj_close": c}
        for d, c in closes.items()
    ]


def _old_union_above_200d_ma(
    prices: pd.DataFrame, as_of: date, ma_long: int = _MA_LONG
) -> pd.Series:
    """The pre-fix implementation, inlined verbatim for the no-op comparison."""

    wide = _wide_close(prices, as_of)
    if wide.empty:
        return pd.Series(dtype=bool)
    ma = wide.rolling(window=ma_long, min_periods=ma_long).mean().iloc[-1]
    close = wide.iloc[-1]
    return (close > ma).fillna(False)


# --- (a) MULTI-CALENDAR FIX ---------------------------------------------------


def test_multi_calendar_uptrend_resolves_above_true() -> None:
    """Two tickers on DIFFERENT calendars (HK-like vs A-share-like). Their union
    injects cross-ticker NaN gaps. A ticker with >= 200 of its OWN rising
    observations must read above_MA=True — it was False under the union bug."""

    # HK-like ticker trades Mon/Wed/Fri; A-like trades Tue/Thu. Their union has a
    # NaN in every HK row for the A ticker and vice-versa, exactly like a real
    # HK + mainland-A refresh. Give each 260 own observations, both uptrending.
    hk_days: list[date] = []
    a_days: list[date] = []
    d = _AS_OF - timedelta(days=800)
    while d <= _AS_OF:
        if d.weekday() in (0, 2, 4):  # Mon/Wed/Fri
            hk_days.append(d)
        elif d.weekday() in (1, 3):  # Tue/Thu
            a_days.append(d)
        d += timedelta(days=1)
    hk_days = hk_days[-260:]
    a_days = a_days[-260:]
    # Ensure both trade on the final union date so the "latest close" is real.
    hk_days[-1] = _AS_OF
    a_days[-1] = _AS_OF

    # Clear uptrend: linear ramp 100 -> 200 over each ticker's own observations.
    hk = {d: 100.0 + i for i, d in enumerate(hk_days)}
    a = {d: 100.0 + i for i, d in enumerate(a_days)}

    prices = pd.DataFrame(_rows("HKUP", hk) + _rows("AUP", a))
    prices["date"] = pd.to_datetime(prices["date"])

    result = above_200d_ma(prices, _AS_OF, _MA_LONG)
    # Fixed: latest close (top of ramp) > 200D MA -> True for both.
    assert bool(result["HKUP"]) is True
    assert bool(result["AUP"]) is True

    # And prove the bug was real: the OLD union computation reads False here.
    old = _old_union_above_200d_ma(prices, _AS_OF, _MA_LONG)
    assert bool(old["HKUP"]) is False
    assert bool(old["AUP"]) is False


# --- (b) ZERO-REGRESSION NO-OP ------------------------------------------------


def test_single_calendar_is_byte_identical_to_old_union() -> None:
    """On a single (shared) calendar with NO cross-ticker NaN gaps, the fixed
    per-ticker logic must equal the OLD union-frame computation exactly. This is
    the live ETF-proxy path (MCHI/FXI/KWEB/ASHR, one US calendar)."""

    days = [
        _AS_OF - timedelta(days=k)
        for k in range(0, 300)
    ][::-1]

    specs = {
        "MCHI": lambda i: 100.0 + 0.5 * i,      # steady uptrend
        "FXI": lambda i: 200.0 - 0.3 * i,       # steady downtrend
        "KWEB": lambda i: 150.0,                # flat (close == MA edge)
        "ASHR": lambda i: 120.0 + (i % 7) - 3,  # choppy, no trend
    }
    rows: list[dict[str, object]] = []
    for ticker, fn in specs.items():
        for i, dd in enumerate(days):
            rows.append(
                {"date": dd.isoformat(), "ticker": ticker, "adj_close": fn(i)}
            )
    prices = pd.DataFrame(rows)
    prices["date"] = pd.to_datetime(prices["date"])

    new = above_200d_ma(prices, _AS_OF, _MA_LONG)
    old = _old_union_above_200d_ma(prices, _AS_OF, _MA_LONG)
    # Byte-identical index, dtype, and boolean values. ``check_names=False``
    # because the OLD path incidentally stamped the last-row timestamp as the
    # Series ``.name`` (a cosmetic label no consumer — trend_pass /
    # regional_risk_off — ever reads); the boolean data is identical.
    pd.testing.assert_series_equal(
        new.sort_index(), old.sort_index(), check_names=False
    )
    assert list(new.sort_index().items()) == list(old.sort_index().items())


# --- (c) INSUFFICIENT HISTORY -------------------------------------------------


def test_insufficient_history_resolves_false() -> None:
    """A ticker with fewer than ma_long own observations -> NaN MA -> False."""

    days = [_AS_OF - timedelta(days=k) for k in range(0, 150)][::-1]  # < 200
    short = {d: 100.0 + i for i, d in enumerate(days)}  # uptrend but too short
    prices = pd.DataFrame(_rows("SHORT", short))
    prices["date"] = pd.to_datetime(prices["date"])

    result = above_200d_ma(prices, _AS_OF, _MA_LONG)
    assert bool(result["SHORT"]) is False
