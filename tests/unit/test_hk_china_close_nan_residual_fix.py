"""B093 F001 — regression tests for the B091-O1 close-NaN residual in
``above_200d_ma``.

B091 fixed the *MA* to compute on each ticker's OWN trading calendar, but the
compared close was still ``wide.iloc[-1]`` — the raw last row of the UNION
frame. When the union's final date is a trading HOLIDAY for a given ticker (e.g.
the union last date is a mainland-A / US-only day while an HK name did not
trade), that ticker's cell on the last row is NaN → ``close > ma`` is NaN →
``fillna(False)`` → a spurious "below MA" / false-defensive quarter. On the real
24-quarter data this fired on ~2 quarters.

The fix compares each ticker's own LAST VALID close (``wide.ffill().iloc[-1]``).
These tests pin:

* (a) MULTI-CALENDAR HOLIDAY FIX — an uptrending ticker whose OWN last close is
  above its MA now reads ``above_MA=True`` even when the union's final row is a
  holiday for it (NaN). The pre-fix raw-last-row path read ``False`` there.
* (b) ★ZERO-REGRESSION — on a single-calendar gap-free frame the fixed output is
  byte-identical to the pre-fix raw-last-row path (live US-only ETF proxy
  unchanged).
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from trade.strategies.hk_china_momentum.factors import (
    _latest_ma_own_calendar,
    _wide_close,
    above_200d_ma,
)

_AS_OF = date(2024, 6, 28)
_MA_LONG = 200


def _rows(ticker: str, closes: dict[date, float]) -> list[dict[str, object]]:
    return [
        {"date": d.isoformat(), "ticker": ticker, "adj_close": c}
        for d, c in closes.items()
    ]


def _prefix_raw_last_row_above_200d_ma(
    prices: pd.DataFrame, as_of: date, ma_long: int = _MA_LONG
) -> pd.Series:
    """The B091 implementation (own-calendar MA) BUT with the residual close bug:
    ``close = wide.iloc[-1]`` (raw union last row). Inlined verbatim so the test
    proves both the multi-calendar defect and the single-calendar no-op against
    the exact pre-B093 behaviour."""

    wide = _wide_close(prices, as_of)
    if wide.empty:
        return pd.Series(dtype=bool)
    close = wide.iloc[-1]  # residual bug: raw union last row (may be NaN)
    ma = wide.apply(lambda col: _latest_ma_own_calendar(col, ma_long))
    return (close > ma).fillna(False)


# --- (a) MULTI-CALENDAR HOLIDAY FIX -------------------------------------------


def test_holiday_last_row_no_longer_false_defensive() -> None:
    """An uptrending HK-like ticker that did NOT trade on the union's final date
    (a mainland-A/US-only day) must still read above_MA=True after the fix. The
    pre-fix raw-last-row path read False (a spurious false-defensive)."""

    # HK ticker trades Mon..Thu; the "other market" ticker trades Fri. Arrange so
    # the union's LAST date is a Friday — an HK holiday — so HK's last union cell
    # is NaN, exactly the B091-O1 condition.
    #
    # _AS_OF (2024-06-28) is a Friday. Build ~320 calendar-days back.
    hk_days: list[date] = []
    other_days: list[date] = []
    d = _AS_OF - timedelta(days=460)
    while d <= _AS_OF:
        if d.weekday() in (0, 1, 2, 3):  # Mon..Thu -> HK
            hk_days.append(d)
        elif d.weekday() == 4:  # Fri -> the other market
            other_days.append(d)
        d += timedelta(days=1)

    # 260 own rising observations each (well over the 200 MA warmup).
    hk_days = hk_days[-260:]
    other_days = other_days[-40:]
    # The union's final date must be an "other" (Friday) date so HK is NaN there.
    assert other_days[-1] == _AS_OF
    assert hk_days[-1] < _AS_OF  # HK did not trade on the union's last date

    # Clear uptrend for HK: linear ramp so the last real close >> its 200D MA.
    hk = {d: 100.0 + i for i, d in enumerate(hk_days)}
    other = {d: 500.0 + i for i, d in enumerate(other_days)}

    prices = pd.DataFrame(_rows("HKUP", hk) + _rows("OTHR", other))
    prices["date"] = pd.to_datetime(prices["date"])

    fixed = above_200d_ma(prices, _AS_OF, _MA_LONG)
    buggy = _prefix_raw_last_row_above_200d_ma(prices, _AS_OF, _MA_LONG)

    # FIX: HK's own last valid close (top of ramp) > its 200D MA -> True.
    assert bool(fixed["HKUP"]) is True
    # PROVE the residual bug was real: raw-last-row NaN -> fillna(False).
    assert bool(buggy["HKUP"]) is False


# --- (b) ZERO-REGRESSION — single-calendar byte-identical ---------------------


def test_single_calendar_gap_free_is_byte_identical() -> None:
    """On one shared, gap-free calendar (the live US-only proxy
    MCHI/FXI/KWEB/ASHR) the fixed ``ffill().iloc[-1]`` close equals the raw
    ``iloc[-1]`` close exactly — every row is fully populated, so ffill is a
    no-op. The output must be byte-identical to the pre-fix path."""

    days = [_AS_OF - timedelta(days=k) for k in range(0, 300)][::-1]
    specs = {
        "MCHI": lambda i: 100.0 + 0.5 * i,      # steady uptrend
        "FXI": lambda i: 200.0 - 0.3 * i,       # steady downtrend
        "KWEB": lambda i: 150.0,                # flat (close == MA edge)
        "ASHR": lambda i: 120.0 + (i % 7) - 3,  # choppy, no trend
    }
    rows: list[dict[str, object]] = []
    for ticker, fn in specs.items():
        for i, dd in enumerate(days):
            rows.append({"date": dd.isoformat(), "ticker": ticker, "adj_close": fn(i)})
    prices = pd.DataFrame(rows)
    prices["date"] = pd.to_datetime(prices["date"])

    fixed = above_200d_ma(prices, _AS_OF, _MA_LONG)
    buggy = _prefix_raw_last_row_above_200d_ma(prices, _AS_OF, _MA_LONG)

    pd.testing.assert_series_equal(
        fixed.sort_index(), buggy.sort_index(), check_names=False
    )
    assert list(fixed.sort_index().items()) == list(buggy.sort_index().items())
