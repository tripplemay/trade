"""B063 F004 — assembly-layer tests for the proxy-vs-real comparison runner.

Pins the bits the runner ADDS on top of the F003 harness: building the two
same-caliber USD frames from one unified prices frame (proxy ETFs pass through
USD, CN/HK names convert at the as-of FX rate), deriving the shared
quarter-end calendar from the INTERSECTION of the two calendars (so a
calendar mismatch never forces a side defensive), the end-to-end run, the
report payload's run-metadata + coverage block, and the honest no-overlap
failure. Synthetic frames only — no disk, no network, no real CN/HK data.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from trade.backtest.hk_china_comparison_runner import (
    build_runner_payload,
    build_usd_frames,
    run_comparison_from_unified,
    shared_quarterly_signal_dates,
)
from trade.backtest.monthly import BacktestError
from trade.data.fx import FxConverter
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters

_DEFENSIVE = "SGOV"
_CNY_RATE = 7.1
_HKD_RATE = 7.8
# A few real names spanning HK (HKD) + A-share (CNY); a subset of the wide
# universe is enough to exercise FX conversion + selection.
_REAL_HK = ("0700.HK", "9988.HK", "0939.HK")
_REAL_CN = ("600519.SH", "600036.SH")


def _converter() -> FxConverter:
    # One early observation each → as-of lookup resolves for every later date.
    return FxConverter(
        {
            "CNY": [(date(2022, 12, 30), _CNY_RATE)],
            "HKD": [(date(2022, 12, 30), _HKD_RATE)],
        }
    )


def _ramp_rows(
    ticker: str, dates: list[pd.Timestamp], start: float, end: float
) -> list[dict[str, object]]:
    n = len(dates)
    rows: list[dict[str, object]] = []
    for i, day in enumerate(dates):
        close = start + (end - start) * (i / (n - 1)) if n > 1 else start
        rows.append(
            {
                "date": day,
                "ticker": ticker,
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "adj_close": close,
                "volume": 1000,
            }
        )
    return rows


def _unified_frame(*, drop_proxy_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Synthetic unified prices: proxy ETFs (USD) + real CN/HK (local) + SGOV.

    ~18 months of business days → several confirmed quarters. ``drop_proxy_date``
    removes one trading date from the proxy side only, to prove the shared
    calendar is the intersection."""

    dates = list(pd.bdate_range("2023-01-02", "2024-06-28"))
    rows: list[dict[str, object]] = []
    # Proxy ETFs (already USD) — gentle ramps.
    for ticker in ("MCHI", "FXI", "KWEB", "ASHR"):
        proxy_dates = [d for d in dates if d != drop_proxy_date] if drop_proxy_date else dates
        rows.extend(_ramp_rows(ticker, proxy_dates, 40.0, 70.0))
    # Real names (local currency) — risers so some pass the trend filter.
    for offset, ticker in enumerate(_REAL_HK + _REAL_CN):
        rows.extend(_ramp_rows(ticker, dates, 100.0, 160.0 + offset * 10))
    # Defensive asset (USD) on both sides.
    rows.extend(_ramp_rows(_DEFENSIVE, dates, 100.0, 100.0))
    return pd.DataFrame(rows)


def test_build_usd_frames_passthrough_and_conversion() -> None:
    frame = _unified_frame()
    proxy_usd, real_usd = build_usd_frames(
        frame, _converter(), proxy_defensive_asset=_DEFENSIVE, real_defensive_asset=_DEFENSIVE
    )
    # Proxy side: only the four ETFs + SGOV, USD unchanged.
    assert set(proxy_usd["ticker"]) == {"MCHI", "FXI", "KWEB", "ASHR", _DEFENSIVE}
    mchi = proxy_usd[proxy_usd["ticker"] == "MCHI"].iloc[0]
    assert mchi["close"] == pytest.approx(40.0)  # USD passthrough

    # Real side: HK converts at HKD rate, A-share at CNY rate, SGOV passes through.
    assert "0700.HK" in set(real_usd["ticker"])
    assert "MCHI" not in set(real_usd["ticker"])
    hk = real_usd[real_usd["ticker"] == "0700.HK"].iloc[0]
    assert hk["close"] == pytest.approx(100.0 / _HKD_RATE)
    cn = real_usd[real_usd["ticker"] == "600519.SH"].iloc[0]
    assert cn["close"] == pytest.approx(100.0 / _CNY_RATE)
    sgov = real_usd[real_usd["ticker"] == _DEFENSIVE].iloc[0]
    assert sgov["close"] == pytest.approx(100.0)  # USD passthrough


def test_shared_signal_dates_are_intersection() -> None:
    full = _unified_frame()
    proxy_usd, real_usd = build_usd_frames(
        full, _converter(), proxy_defensive_asset=_DEFENSIVE, real_defensive_asset=_DEFENSIVE
    )
    baseline = set(shared_quarterly_signal_dates(proxy_usd, real_usd))
    assert baseline  # several confirmed quarter-ends

    # Drop a real quarter-end from the proxy calendar → it must leave the shared set.
    dropped = sorted(baseline)[1]
    holed = _unified_frame(drop_proxy_date=pd.Timestamp(dropped))
    proxy_holed, real_holed = build_usd_frames(
        holed, _converter(), proxy_defensive_asset=_DEFENSIVE, real_defensive_asset=_DEFENSIVE
    )
    after = set(shared_quarterly_signal_dates(proxy_holed, real_holed))
    assert dropped not in after  # not a trading date in BOTH → excluded


def test_run_comparison_end_to_end_and_payload() -> None:
    frame = _unified_frame()
    converter = _converter()
    result, signal_dates = run_comparison_from_unified(
        frame, converter, real_parameters=HkChinaRealParameters(top_n=3)
    )
    assert len(signal_dates) >= 2
    assert result.n_signal_dates == len(signal_dates)
    assert result.usd_caliber is True
    assert result.proxy.holding_kind == "diversified_etf"
    assert result.real.holding_kind == "single_name"
    assert result.real.selection_top_n == 3

    proxy_usd, real_usd = build_usd_frames(
        frame, converter, proxy_defensive_asset=_DEFENSIVE, real_defensive_asset=_DEFENSIVE
    )
    payload = build_runner_payload(result, signal_dates, proxy_usd, real_usd)
    meta = payload["run_metadata"]
    assert isinstance(meta, dict)
    assert meta["n_signal_dates"] == len(signal_dates)
    assert len(meta["signal_dates"]) == len(signal_dates)  # type: ignore[arg-type]
    real_cov = meta["real_coverage"]
    assert isinstance(real_cov, dict)
    # Every real name we seeded has data; the names we did NOT seed are flagged.
    for ticker in _REAL_HK + _REAL_CN:
        assert ticker in real_cov["names_with_data"]  # type: ignore[operator]
    assert real_cov["names_missing_data"]  # the wide universe is only partly seeded


def test_no_overlap_raises_honestly() -> None:
    # Real names only — no proxy/real calendar overlap, no shared quarter-ends.
    dates = list(pd.bdate_range("2023-01-02", "2024-06-28"))
    rows: list[dict[str, object]] = []
    rows.extend(_ramp_rows("0700.HK", dates, 100.0, 160.0))
    rows.extend(_ramp_rows(_DEFENSIVE, dates, 100.0, 100.0))
    frame = pd.DataFrame(rows)  # no proxy ETFs at all
    with pytest.raises(BacktestError, match="shared quarter-end"):
        run_comparison_from_unified(frame, _converter())
