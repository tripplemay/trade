"""Price-only factors for the BL-B011-S2 HK-China Momentum satellite.

Three signals, all derivable from daily prices (design doc §7):

* **composite momentum** — ``0.4·r3m + 0.3·r6m + 0.3·r12m`` (§7.1). Each
  ``rNm`` is a simple trailing return (no 12-1 skip), reusing the B025
  :func:`momentum_12_1` primitive with ``skip_months=0``.
* **trend filter** — ``close > 200D MA`` AND ``r6m > 0`` (§7.2, conservative
  both-conditions version). Boolean per ETF.
* **regional-risk-off** — a portfolio-level defensive trigger (§7.3): the
  China-internet/large-cap proxies (KWEB/MCHI/FXI) are ALL below their 200D
  MA, OR every universe ETF's 6-month return is negative. HSI is not used
  (it is outside the data-refresh universe — planner decision); manual
  policy overrides are a human judgement and are not encoded (research-only).

Every function is pure (no IO / no mutation / no globals) and re-filters to
``date <= as_of`` so it cannot leak future data. NaN is returned for tickers
without enough history.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from trade.strategies.us_quality_momentum.factors import momentum_12_1

# China-internet / large-cap proxies for the regional-risk gate (design §7.3).
DEFAULT_REGIONAL_RISK_PROXIES: tuple[str, ...] = ("KWEB", "MCHI", "FXI")
DEFAULT_MA_LONG = 200


def _wide_close(prices: pd.DataFrame, as_of: date) -> pd.DataFrame:
    """Wide ``date × ticker`` adjusted-close frame, visible on/before ``as_of``."""

    missing = [c for c in ("date", "ticker", "adj_close") if c not in prices.columns]
    if missing:
        raise ValueError(f"prices frame missing columns: {missing}")
    visible = prices.loc[prices["date"] <= pd.Timestamp(as_of)].copy()
    visible["date"] = pd.to_datetime(visible["date"])
    return visible.pivot_table(
        index="date", columns="ticker", values="adj_close", aggfunc="last"
    ).sort_index()


def trailing_return(prices: pd.DataFrame, as_of: date, months: int) -> pd.Series:
    """Simple trailing ``months``-month return per ticker (no skip)."""

    return momentum_12_1(prices, as_of, lookback_months=months, skip_months=0)


def composite_momentum(
    prices: pd.DataFrame,
    as_of: date,
    *,
    w3: float = 0.4,
    w6: float = 0.3,
    w12: float = 0.3,
) -> pd.Series:
    """``w3·r3m + w6·r6m + w12·r12m`` per ETF (design §7.1).

    A ticker missing any of the three anchors yields NaN (it is then ineligible
    downstream — we never score on partial history)."""

    r3 = trailing_return(prices, as_of, 3)
    r6 = trailing_return(prices, as_of, 6)
    r12 = trailing_return(prices, as_of, 12)
    return w3 * r3 + w6 * r6 + w12 * r12


def return_6m(prices: pd.DataFrame, as_of: date) -> pd.Series:
    """6-month trailing return per ticker (design §7.2 / §7.3 input)."""

    return trailing_return(prices, as_of, 6)


def _latest_ma_own_calendar(col: pd.Series, ma_long: int) -> float:
    """Latest ``ma_long``-day MA of one ticker, on ITS OWN trading calendar.

    ``_wide_close`` unions every ticker's calendar, so a column carries NaN on
    dates the ticker did not trade. Dropping those NaNs *before* the rolling
    window makes ``min_periods`` count real observations, not union rows. A
    ticker with fewer than ``ma_long`` real observations yields NaN (insufficient
    trend evidence). On a single-calendar (gap-free) column ``dropna`` removes
    nothing, so this equals the plain per-column rolling exactly."""

    own = col.dropna()
    ma = own.rolling(window=ma_long, min_periods=ma_long).mean()
    return float("nan") if ma.empty else float(ma.iloc[-1])


def above_200d_ma(
    prices: pd.DataFrame, as_of: date, ma_long: int = DEFAULT_MA_LONG
) -> pd.Series:
    """Boolean per ETF: latest close strictly above its 200-day MA.

    The MA is computed on each ticker's own trading calendar (see
    :func:`_latest_ma_own_calendar`): cross-market universes (HK + mainland-A +
    US) inject NaN gaps into every column, which would otherwise starve the
    ``min_periods=ma_long`` window and read "below MA" forever. On a
    single-calendar frame the per-ticker dropna is a no-op, so the result is
    byte-identical to a plain union-frame rolling.

    Tickers without ``ma_long`` days of history (MA is NaN) resolve to
    ``False`` — insufficient trend evidence is treated as "not above"."""

    wide = _wide_close(prices, as_of)
    if wide.empty:
        return pd.Series(dtype=bool)
    close = wide.iloc[-1]
    ma = wide.apply(lambda col: _latest_ma_own_calendar(col, ma_long))
    return (close > ma).fillna(False)


def trend_pass(
    prices: pd.DataFrame, as_of: date, ma_long: int = DEFAULT_MA_LONG
) -> pd.Series:
    """Boolean per ETF: ``close > 200D MA`` AND ``r6m > 0`` (design §7.2)."""

    above = above_200d_ma(prices, as_of, ma_long)
    r6 = return_6m(prices, as_of)
    passed = above & (r6 > 0).fillna(False)
    return passed.reindex(above.index).fillna(False)


def regional_risk_off(
    prices: pd.DataFrame,
    as_of: date,
    *,
    ma_long: int = DEFAULT_MA_LONG,
    proxies: tuple[str, ...] = DEFAULT_REGIONAL_RISK_PROXIES,
) -> bool:
    """Portfolio-level defensive trigger (design §7.3, deterministic subset).

    Returns ``True`` when EITHER:

    * every available proxy (KWEB/MCHI/FXI) is below its 200D MA, OR
    * every universe ETF with a 6-month return has a negative one.

    HSI and bid/ask-spread / manual-policy triggers are intentionally omitted
    (HSI is outside the universe; manual overrides are research-only)."""

    above = above_200d_ma(prices, as_of, ma_long)
    available_proxies = [p for p in proxies if p in above.index]
    all_proxies_below = bool(available_proxies) and all(
        not bool(above[p]) for p in available_proxies
    )

    r6 = return_6m(prices, as_of).dropna()
    all_six_month_negative = bool(len(r6)) and bool((r6 < 0).all())

    return all_proxies_below or all_six_month_negative
