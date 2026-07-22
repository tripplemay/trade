"""B111 F001 (P0-1) regression: the Global ETF Momentum sleeve must rank over
the ETF universe only (no individual equities) and interpret its 3/6/9 windows
as MONTHS even when fed a daily production price feed.

Diagnosis §2/§6 F1: production fed the sleeve a daily unified CSV mixing 15 ETFs
with 27 individual equities, so it ranked 42 mixed symbols with 3/6/9-*day*
windows — an unvalidated signal that put CAT/HD (single stocks) into the live
book. These tests fail on the pre-fix code (equities selected / daily lookback)
and pass on the fixed code.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from trade.backtest.master_portfolio import _resolve_child_weights
from trade.data.loader import PriceBar
from trade.portfolio.master import default_master_portfolio_parameters
from trade.strategies.global_etf_momentum import (
    GLOBAL_ETF_MOMENTUM_UNIVERSE,
    MomentumParameters,
    MomentumWindow,
    filter_to_universe,
    generate_momentum_signal,
    prepare_momentum_records,
    resample_to_month_end,
)
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
from trade.strategies.risk_parity import RiskParityParameters
from trade.strategies.us_quality_momentum.parameters import (
    UsQualityMomentumParameters,
)

_SHORT_PARAMS = MomentumParameters(
    top_n=1,
    defensive_asset="AGG",
    momentum_windows=(MomentumWindow(periods=1, weight=1.0),),
    trend_window=1,
    require_positive_trend_return=False,
)


def _bar(symbol: str, day: date, price: float) -> PriceBar:
    return PriceBar(
        date=day,
        symbol=symbol,
        open=price,
        close=price,
        adjusted_close=price,
        volume=1_000_000,
    )


def _daily_ramp(
    symbol: str, start: date, end: date, start_price: float, end_price: float
) -> list[PriceBar]:
    """Weekday bars linearly ramping ``start_price`` → ``end_price``."""

    span = (end - start).days
    records: list[PriceBar] = []
    for offset in range(span + 1):
        day = start + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        price = start_price + (end_price - start_price) * (offset / span)
        records.append(_bar(symbol, day, price))
    return records


def _momentum_sleeve():
    params = default_master_portfolio_parameters()
    return next(s for s in params.sleeves if s.strategy_id == "global_etf_momentum")


def _resolve_momentum(records: tuple[PriceBar, ...], signal_date: date, params):
    return _resolve_child_weights(
        _momentum_sleeve(),
        records=records,
        signal_date=signal_date,
        defensive_asset="SGOV",
        momentum_params=params,
        risk_parity_params=RiskParityParameters(),
        us_quality_params=UsQualityMomentumParameters(),
        hk_china_params=HkChinaMomentumParameters(),
    )


# ── helper-level unit tests ──────────────────────────────────────────────────


def test_filter_to_universe_drops_individual_equities_keeps_etfs() -> None:
    records = (
        _bar("SPY", date(2024, 1, 31), 100.0),
        _bar("CAT", date(2024, 1, 31), 100.0),
        _bar("HD", date(2024, 1, 31), 100.0),
        _bar("AGG", date(2024, 1, 31), 100.0),
    )
    kept = filter_to_universe(records, GLOBAL_ETF_MOMENTUM_UNIVERSE)
    symbols = {bar.symbol for bar in kept}
    assert symbols == {"SPY", "AGG"}
    assert "CAT" not in symbols and "HD" not in symbols


def test_resample_collapses_daily_to_one_bar_per_month() -> None:
    daily = tuple(_daily_ramp("SPY", date(2024, 1, 2), date(2024, 4, 30), 100.0, 130.0))
    collapsed = [bar for bar in resample_to_month_end(daily) if bar.symbol == "SPY"]
    months = {(bar.date.year, bar.date.month) for bar in collapsed}
    assert len(collapsed) == len(months) == 4  # Jan..Apr, one bar each
    # Each surviving bar is the last trading day of its month.
    assert collapsed[-1].date == date(2024, 4, 30)


def test_resample_is_idempotent_on_monthly_input() -> None:
    """Month-end resampling must be a no-op on already-monthly data — this is
    what guarantees the validated backtest (monthly fixture) is unchanged."""

    monthly = (
        _bar("SPY", date(2024, 1, 31), 100.0),
        _bar("SPY", date(2024, 2, 29), 105.0),
        _bar("SPY", date(2024, 3, 29), 110.0),
    )
    assert resample_to_month_end(monthly) == monthly


def test_prepare_pipeline_excludes_equities_and_keeps_monthly_etfs() -> None:
    start, end = date(2024, 1, 2), date(2024, 6, 28)
    records = tuple(
        _daily_ramp("SPY", start, end, 100.0, 120.0)
        + _daily_ramp("CAT", start, end, 100.0, 160.0)
        + _daily_ramp("AGG", start, end, 100.0, 101.0)
    )
    prepared = prepare_momentum_records(
        records, parameters=_SHORT_PARAMS, signal_date=date(2024, 6, 28)
    )
    symbols = {bar.symbol for bar in prepared}
    assert symbols == {"SPY", "AGG"}  # CAT (equity) excluded
    spy = [bar for bar in prepared if bar.symbol == "SPY"]
    assert len(spy) == len({(b.date.year, b.date.month) for b in spy})  # monthly


def test_prepare_drops_short_history_etf_without_aborting_sleeve() -> None:
    """A recently-listed ETF (too few month-ends) is dropped as a candidate,
    not allowed to abort the whole sleeve — long-history ETFs still rank."""

    params = MomentumParameters(
        top_n=1,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=3, weight=1.0),),
        trend_window=2,
        require_positive_trend_return=False,
    )
    signal_date = date(2024, 6, 28)
    long_history = _daily_ramp("SPY", date(2024, 1, 2), signal_date, 100.0, 120.0)
    short_history = _daily_ramp("QQQ", date(2024, 5, 1), signal_date, 100.0, 110.0)
    defensive = _daily_ramp("AGG", date(2024, 1, 2), signal_date, 100.0, 101.0)
    prepared = prepare_momentum_records(
        tuple(long_history + short_history + defensive),
        parameters=params,
        signal_date=signal_date,
    )
    symbols = {bar.symbol for bar in prepared}
    assert "SPY" in symbols  # 6 month-ends > required 3
    assert "QQQ" not in symbols  # only ~2 month-ends ≤ required 3 → dropped
    # And the sleeve still produces a signal (no MomentumSignalError raised).
    signal = generate_momentum_signal(prepared, params, signal_date)
    assert signal.target_weights


# ── behavioural: monthly (not daily) lookback semantics ──────────────────────


def test_momentum_uses_monthly_not_daily_lookback() -> None:
    """A 3-period window must span 3 MONTHS, not 3 days. Construct a series that
    rises month over month but dips in the final days, so the 3-month return is
    positive while the 3-day return is negative — the sign disambiguates."""

    month_ends = {
        date(2024, 1, 31): 100.0,
        date(2024, 2, 29): 105.0,
        date(2024, 3, 29): 110.0,
        date(2024, 4, 30): 120.0,
    }
    # May: rise then dip into month-end (last bar 130 < prior days ~134).
    may_path = {
        date(2024, 5, 24): 136.0,
        date(2024, 5, 27): 135.0,
        date(2024, 5, 28): 134.0,
        date(2024, 5, 29): 133.0,
        date(2024, 5, 30): 132.0,
        date(2024, 5, 31): 130.0,
    }
    records: list[PriceBar] = []
    for day, price in {**month_ends, **may_path}.items():
        records.append(_bar("SPY", day, price))
        records.append(_bar("AGG", day, price * 0.5))  # defensive, present
    records_t = tuple(records)
    signal_date = date(2024, 5, 31)
    params = MomentumParameters(
        top_n=1,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=3, weight=1.0),),
        trend_window=2,
        require_positive_trend_return=False,
    )

    prepared = prepare_momentum_records(
        records_t, parameters=params, signal_date=signal_date
    )
    prepared_signal = generate_momentum_signal(prepared, params, signal_date)
    prepared_spy = next(a for a in prepared_signal.ranked_assets if a.symbol == "SPY")
    # Month-ends [100,105,110,120,130]: 3-month return = 130/105 - 1.
    assert prepared_spy.momentum_score == pytest.approx(130.0 / 105.0 - 1.0)
    assert prepared_spy.momentum_score > 0

    # Pre-fix behaviour (raw daily feed): 3-*day* lookback into the final dip is
    # NEGATIVE — the opposite sign, proving the semantics actually changed.
    raw_signal = generate_momentum_signal(records_t, params, signal_date)
    raw_spy = next(a for a in raw_signal.ranked_assets if a.symbol == "SPY")
    assert raw_spy.momentum_score < 0


# ── behavioural: individual equities never selected end-to-end ───────────────


def test_resolve_child_weights_never_holds_individual_equities() -> None:
    """Even when single stocks carry the strongest momentum, the sleeve must
    not hold them — the ETF whitelist is applied inside the Master dispatch."""

    start, end = date(2024, 1, 2), date(2024, 5, 31)
    records = tuple(
        _daily_ramp("SPY", start, end, 100.0, 110.0)
        + _daily_ramp("QQQ", start, end, 100.0, 112.0)
        + _daily_ramp("CAT", start, end, 100.0, 150.0)  # strongest — would win
        + _daily_ramp("HD", start, end, 100.0, 140.0)
        + _daily_ramp("AGG", start, end, 100.0, 101.0)
    )
    signal_date = date(2024, 5, 31)
    params = MomentumParameters(
        top_n=2,
        defensive_asset="AGG",
        momentum_windows=(MomentumWindow(periods=2, weight=1.0),),
        trend_window=2,
        require_positive_trend_return=False,
    )

    weights = _resolve_momentum(records, signal_date, params)
    assert "CAT" not in weights
    assert "HD" not in weights
    assert set(weights).issubset({"SPY", "QQQ", "AGG"})

    # Contrast: the raw (pre-fix) feed WOULD select the single stocks.
    raw_signal = generate_momentum_signal(records, params, signal_date)
    assert "CAT" in raw_signal.selected_assets


def test_momentum_universe_is_the_expected_etf_set() -> None:
    """Pin the whitelist so an accidental edit that re-admits equities fails
    here (workbench keeps a separate drift-guard vs ``ETF_UNIVERSE``)."""

    assert frozenset(
        {
            "AGG",
            "ASHR",
            "DBC",
            "EEM",
            "FXI",
            "GLD",
            "IEF",
            "KWEB",
            "MCHI",
            "QQQ",
            "SGOV",
            "SPY",
            "TLT",
            "VEA",
            "VWO",
        }
    ) == GLOBAL_ETF_MOMENTUM_UNIVERSE
    # The single stocks that polluted the live book (and typical us_quality
    # names) must never be candidates.
    for stock in ("CAT", "HD", "JNJ", "AAPL", "MSFT", "NVDA", "UNH"):
        assert stock not in GLOBAL_ETF_MOMENTUM_UNIVERSE
