"""B063 F002 — real-data HK-China research strategy (parameters / construction /
signal), with the methodology-critical point-in-time no-leakage proof.

Deterministic calendar-day ramps exercise the reused momentum/trend/regional-
risk factors over real individual-stock tickers: generic top-N equal-weight
selection, the per-name cap rotating excess to the defensive asset, the
no-survivor and regional-risk-off defensive paths. The signal tests prove the
local→USD pipeline and — the core spec §2 guarantee — that **future price and
future FX are inert**: the signal at ``as_of`` is identical whether or not the
inputs carry data dated after ``as_of``.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest

from trade.data.fx import FxConverter
from trade.strategies.hk_china_real.construction import build_real_portfolio
from trade.strategies.hk_china_real.parameters import (
    HkChinaRealParameters,
    ParameterValidationError,
)
from trade.strategies.hk_china_real.signal import generate_real_signal

_AS_OF = date(2024, 6, 28)
_PARAMS = HkChinaRealParameters()

# Real-universe tickers (rising names + the three risk bellwethers).
_RISERS = ("3690.HK", "1810.HK", "9618.HK", "0939.HK", "0883.HK")
_BELLWETHERS = ("0700.HK", "9988.HK", "600519.SH")


def _ramp(
    specs: dict[str, tuple[float, float]],
    *,
    as_of: date = _AS_OF,
    n_days: int = 420,
) -> pd.DataFrame:
    """Long-format daily prices: each ticker a linear start→end ramp over the
    ``n_days`` calendar days ending at ``as_of`` (one bar per calendar day, so
    the 200D MA + 12m momentum anchors all resolve)."""

    start_day = as_of - timedelta(days=n_days - 1)
    rows: list[dict[str, object]] = []
    for ticker, (start, end) in specs.items():
        for i in range(n_days):
            d = start_day + timedelta(days=i)
            close = start + (end - start) * (i / (n_days - 1))
            rows.append(
                {
                    "date": pd.Timestamp(d),
                    "ticker": ticker,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "adj_close": close,
                    "volume": 1000,
                }
            )
    return pd.DataFrame(rows)


def _flat_fx(rate: float = 7.0) -> FxConverter:
    # One early observation; as-of forward-fill covers every later bar date.
    return FxConverter({"HKD": [(date(2000, 1, 1), rate)], "CNY": [(date(2000, 1, 1), rate)]})


# --- parameters ---


def test_parameters_defaults_and_hash_determinism() -> None:
    assert _PARAMS.top_n == 6
    assert _PARAMS.strategy_id == "hk_china_real"
    assert _PARAMS.parameter_hash() == HkChinaRealParameters().parameter_hash()
    assert _PARAMS.parameter_hash() != HkChinaRealParameters(top_n=3).parameter_hash()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"top_n": 0},
        {"top_n": 99},
        {"max_position_weight": 0.0},
        {"max_position_weight": 1.5},
        {"ma_long": 1},
        {"rebalance_frequency": "weekly"},
        {"defensive_asset": ""},
    ],
)
def test_parameters_reject_invalid(kwargs: dict[str, object]) -> None:
    with pytest.raises(ParameterValidationError):
        HkChinaRealParameters(**kwargs)  # type: ignore[arg-type]


# --- construction ---


def test_top_n_equal_weight_selection() -> None:
    # Five risers with strictly increasing total return + flat bellwethers (so no
    # risk-off). top_n=3 must pick the three highest-momentum risers, equal weight.
    specs = {t: (40.0, 40.0 + 10 * (i + 1)) for i, t in enumerate(_RISERS)}
    specs.update({t: (40.0, 60.0) for t in _BELLWETHERS})  # rising → not risk-off
    frame = _ramp(specs)
    params = HkChinaRealParameters(top_n=3)
    portfolio = build_real_portfolio(
        prices=frame,
        universe_tickers=_RISERS + _BELLWETHERS,
        as_of=_AS_OF,
        parameters=params,
    )
    # Highest end prices among risers: 9618.HK(90), 0939.HK(80), 0883.HK(70).
    assert set(portfolio.selected) == {"9618.HK", "0939.HK", "0883.HK"}
    weights = portfolio.as_dict()
    for ticker in portfolio.selected:
        assert weights[ticker] == pytest.approx(1 / 3, abs=1e-6)
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert portfolio.candidates == 8
    assert portfolio.scored == 8  # all have full history


def test_per_name_cap_rotates_excess_to_defensive() -> None:
    specs = {t: (40.0, 40.0 + 10 * (i + 1)) for i, t in enumerate(_RISERS)}
    specs.update({t: (40.0, 60.0) for t in _BELLWETHERS})
    frame = _ramp(specs)
    params = HkChinaRealParameters(top_n=3, max_position_weight=0.25)
    portfolio = build_real_portfolio(
        prices=frame,
        universe_tickers=_RISERS + _BELLWETHERS,
        as_of=_AS_OF,
        parameters=params,
    )
    weights = portfolio.as_dict()
    for ticker in portfolio.selected:
        assert weights[ticker] == pytest.approx(0.25)
    assert weights["SGOV"] == pytest.approx(0.25)  # 1.0 - 3*0.25
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)


def test_no_survivor_goes_defensive() -> None:
    # Everything declining → trend filter rejects all → fully defensive.
    specs = {t: (60.0, 30.0) for t in _RISERS + _BELLWETHERS}
    frame = _ramp(specs)
    portfolio = build_real_portfolio(
        prices=frame,
        universe_tickers=_RISERS + _BELLWETHERS,
        as_of=_AS_OF,
        parameters=_PARAMS,
    )
    assert portfolio.as_dict() == {"SGOV": 1.0}
    assert portfolio.selected == ()
    # All 6m returns negative → the breadth branch fires first.
    assert portfolio.regional_risk_off is True


def test_no_name_passed_trend_goes_defensive() -> None:
    # Isolate the OTHER defensive branch (reason="no_name_passed_trend",
    # risk_off=False), distinct from regional_risk_off: every *universe* name
    # declines (fails the trend filter), but a non-universe name rises so the
    # breadth check (all 6m negative) does NOT fire, and no bellwether is in the
    # frame so the proxy check does NOT fire either.
    universe = ("3690.HK", "1810.HK", "9618.HK")
    specs = {t: (60.0, 30.0) for t in universe}  # declining → fail trend
    specs["0939.HK"] = (40.0, 80.0)  # rising, non-universe, non-bellwether
    frame = _ramp(specs)
    portfolio = build_real_portfolio(
        prices=frame,
        universe_tickers=universe,
        as_of=_AS_OF,
        parameters=_PARAMS,
    )
    assert portfolio.regional_risk_off is False
    assert portfolio.reason == "no_name_passed_trend"
    assert portfolio.selected == ()
    assert portfolio.as_dict() == {"SGOV": 1.0}


def test_regional_risk_off_when_bellwethers_below_ma() -> None:
    # Bellwethers decline (below 200D MA) while other names rise → proxy branch
    # of regional_risk_off fires → fully defensive regardless of the risers.
    specs = {t: (40.0, 80.0) for t in _RISERS}
    specs.update({t: (80.0, 40.0) for t in _BELLWETHERS})  # below MA
    frame = _ramp(specs)
    portfolio = build_real_portfolio(
        prices=frame,
        universe_tickers=_RISERS + _BELLWETHERS,
        as_of=_AS_OF,
        parameters=_PARAMS,
    )
    assert portfolio.regional_risk_off is True
    assert portfolio.reason == "regional_risk_off"
    assert portfolio.as_dict() == {"SGOV": 1.0}


# --- signal (local → USD) + point-in-time no-leakage ---


def test_signal_local_to_usd_selects() -> None:
    specs = {t: (40.0, 40.0 + 10 * (i + 1)) for i, t in enumerate(_RISERS)}
    specs.update({t: (40.0, 60.0) for t in _BELLWETHERS})
    frame = _ramp(specs)
    result = generate_real_signal(
        HkChinaRealParameters(top_n=3), _AS_OF, prices=frame, fx=_flat_fx()
    )
    assert set(result.selected_tickers()) == {"9618.HK", "0939.HK", "0883.HK"}
    assert not result.is_defensive()
    assert sum(result.weights_dict().values()) == pytest.approx(1.0, abs=1e-6)


def test_no_future_leakage_price_and_fx() -> None:
    """Core spec §2 guarantee: data dated after ``as_of`` is inert.

    Build a frame that extends 60 days past ``as_of`` AND an FX series that
    jumps wildly after ``as_of``; the signal computed at ``as_of`` must equal
    the signal computed from inputs truncated at ``as_of``."""

    specs = {t: (40.0, 40.0 + 10 * (i + 1)) for i, t in enumerate(_RISERS)}
    specs.update({t: (40.0, 60.0) for t in _BELLWETHERS})
    # n_days large enough to leave full history both at as_of and at as_of+60.
    future_as_of = _AS_OF + timedelta(days=60)
    full = _ramp(specs, as_of=future_as_of, n_days=480)
    truncated = full[full["date"] <= pd.Timestamp(_AS_OF)].reset_index(drop=True)

    # FX with a post-as_of jump (would corrupt USD prices if it leaked).
    leaky_fx = FxConverter(
        {
            "HKD": [(date(2000, 1, 1), 7.0), (_AS_OF + timedelta(days=1), 999.0)],
            "CNY": [(date(2000, 1, 1), 7.0), (_AS_OF + timedelta(days=1), 999.0)],
        }
    )
    clean_fx = _flat_fx(7.0)

    params = HkChinaRealParameters(top_n=3)
    leaked = generate_real_signal(params, _AS_OF, prices=full, fx=leaky_fx)
    clean = generate_real_signal(params, _AS_OF, prices=truncated, fx=clean_fx)

    assert leaked.weights_dict() == clean.weights_dict()
    assert leaked.selected_tickers() == clean.selected_tickers()


def test_offline_no_data_degrades_to_defensive() -> None:
    # No prices + empty FX (offline trade reality) → honest fully-defensive.
    result = generate_real_signal(
        _PARAMS,
        _AS_OF,
        prices=pd.DataFrame(
            columns=["date", "ticker", "open", "high", "low", "close", "adj_close", "volume"]
        ),
        fx=FxConverter({}),
    )
    assert result.is_defensive()
    assert result.weights_dict() == {"SGOV": 1.0}


# --- additive boundary: research strategy never touches the live Master ---


def test_master_does_not_import_real_strategy() -> None:
    """Spec boundary: hk_china stays proxy in the live Master; the real-data
    research strategy must not be wired into the Master path."""

    master = Path(__file__).resolve().parents[2] / "trade" / "backtest" / "master_portfolio.py"
    assert "hk_china_real" not in master.read_text(encoding="utf-8")
