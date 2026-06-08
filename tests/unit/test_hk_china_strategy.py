"""BL-B011-S2 F002 — HK-China Momentum strategy (parameters / factors /
construction / signal).

Deterministic hand-built price ramps exercise the design-doc rules: momentum
+ trend selection, Top-1 fills the sleeve, Top-2 equal weight, the KWEB
sub-limit rotating excess to the defensive asset, the regional-risk-off gate,
and the no-survivor fallback.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from trade.strategies.hk_china_momentum.construction import build_portfolio
from trade.strategies.hk_china_momentum.parameters import (
    HkChinaMomentumParameters,
    MomentumWeights,
    ParameterValidationError,
)
from trade.strategies.hk_china_momentum.signal import generate_signal

_AS_OF = date(2024, 6, 28)
_UNIVERSE = ("MCHI", "FXI", "KWEB", "ASHR")
_PARAMS = HkChinaMomentumParameters()


def _ramp_prices(
    specs: dict[str, tuple[float, float]],
    *,
    as_of: date = _AS_OF,
    n_days: int = 420,
) -> pd.DataFrame:
    """Long-format daily prices: each ticker a linear ramp start→end over the
    ``n_days`` calendar days ending at ``as_of``."""

    start_day = as_of - timedelta(days=n_days - 1)
    rows: list[dict[str, object]] = []
    for ticker, (start, end) in specs.items():
        for i in range(n_days):
            d = start_day + timedelta(days=i)
            close = start + (end - start) * (i / (n_days - 1))
            rows.append(
                {
                    "date": d.isoformat(),
                    "ticker": ticker,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "adj_close": close,
                    "volume": 1000,
                }
            )
    frame = pd.DataFrame(rows)
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


# --- parameters -----------------------------------------------------------


def test_parameters_defaults_and_hash_stable() -> None:
    p = HkChinaMomentumParameters()
    assert p.strategy_id == "hk_china_momentum"
    assert p.top_n == 2
    assert p.defensive_asset == "SGOV"
    # Hash is deterministic + sensitive to a field change.
    assert p.parameter_hash() == HkChinaMomentumParameters().parameter_hash()
    assert p.parameter_hash() != HkChinaMomentumParameters(top_n=1).parameter_hash()


def test_parameters_reject_invalid() -> None:
    with pytest.raises(ParameterValidationError):
        HkChinaMomentumParameters(top_n=3)
    with pytest.raises(ParameterValidationError):
        HkChinaMomentumParameters(kweb_sublimit=0.0)
    with pytest.raises(ParameterValidationError):
        MomentumWeights(r3m=0.5, r6m=0.3, r12m=0.3)  # sums to 1.1


# --- construction: selection + weighting ----------------------------------


def test_top_two_equal_weight() -> None:
    # MCHI + FXI uptrend (pass), KWEB + ASHR downtrend (fail). Top-2 → 0.5/0.5.
    prices = _ramp_prices(
        {
            "MCHI": (30.0, 60.0),
            "FXI": (25.0, 45.0),
            "KWEB": (60.0, 30.0),
            "ASHR": (50.0, 25.0),
        }
    )
    pf = build_portfolio(
        prices=prices, universe_tickers=_UNIVERSE, as_of=_AS_OF, parameters=_PARAMS
    )
    weights = pf.as_dict()
    assert set(pf.selected) == {"MCHI", "FXI"}
    assert weights["MCHI"] == pytest.approx(0.5)
    assert weights["FXI"] == pytest.approx(0.5)
    assert "SGOV" not in weights
    assert sum(weights.values()) == pytest.approx(1.0)


def test_top_one_fills_sleeve() -> None:
    # Only MCHI passes trend (others down). Top-1 fills the sleeve at 1.0.
    prices = _ramp_prices(
        {
            "MCHI": (30.0, 60.0),
            "FXI": (50.0, 30.0),
            "KWEB": (60.0, 35.0),
            "ASHR": (50.0, 25.0),
        }
    )
    pf = build_portfolio(
        prices=prices, universe_tickers=_UNIVERSE, as_of=_AS_OF, parameters=_PARAMS
    )
    weights = pf.as_dict()
    assert pf.selected == ("MCHI",)
    assert weights["MCHI"] == pytest.approx(1.0)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_kweb_sublimit_routes_excess_to_defensive() -> None:
    # Only KWEB passes (Top-1). Its 0.5 sleeve cap leaves 0.5 → defensive.
    prices = _ramp_prices(
        {
            "KWEB": (30.0, 70.0),
            "MCHI": (60.0, 35.0),
            "FXI": (50.0, 30.0),
            "ASHR": (50.0, 25.0),
        }
    )
    pf = build_portfolio(
        prices=prices, universe_tickers=_UNIVERSE, as_of=_AS_OF, parameters=_PARAMS
    )
    weights = pf.as_dict()
    assert pf.selected == ("KWEB",)
    assert weights["KWEB"] == pytest.approx(0.5)  # kweb_sublimit
    assert weights["SGOV"] == pytest.approx(0.5)
    assert sum(weights.values()) == pytest.approx(1.0)


def test_regional_risk_off_goes_fully_defensive() -> None:
    # All proxies (MCHI/FXI/KWEB) below their 200D MA → risk-off → 100% SGOV.
    prices = _ramp_prices(
        {
            "MCHI": (60.0, 30.0),
            "FXI": (55.0, 28.0),
            "KWEB": (70.0, 32.0),
            "ASHR": (50.0, 26.0),
        }
    )
    pf = build_portfolio(
        prices=prices, universe_tickers=_UNIVERSE, as_of=_AS_OF, parameters=_PARAMS
    )
    assert pf.regional_risk_off is True
    assert pf.as_dict() == {"SGOV": 1.0}


def test_no_survivor_without_risk_off_is_defensive() -> None:
    # Uptrend (not risk-off) but only ~210 days history → 12m momentum NaN →
    # no eligible ETF → defensive, reason no_etf_passed_trend.
    prices = _ramp_prices(
        {t: (30.0, 60.0) for t in _UNIVERSE}, n_days=210
    )
    pf = build_portfolio(
        prices=prices, universe_tickers=_UNIVERSE, as_of=_AS_OF, parameters=_PARAMS
    )
    assert pf.regional_risk_off is False
    assert pf.reason == "no_etf_passed_trend"
    assert pf.as_dict() == {"SGOV": 1.0}


# --- signal end-to-end ----------------------------------------------------


def test_generate_signal_weights_sum_to_one_with_injected_prices() -> None:
    prices = _ramp_prices(
        {
            "MCHI": (30.0, 60.0),
            "FXI": (25.0, 45.0),
            "KWEB": (60.0, 30.0),
            "ASHR": (50.0, 25.0),
        }
    )
    result = generate_signal(_PARAMS, _AS_OF, prices=prices)
    weights = result.weights_dict()
    assert sum(weights.values()) == pytest.approx(1.0)
    assert result.parameters_hash == _PARAMS.parameter_hash()
    assert not result.is_defensive()


def test_generate_signal_on_fixture_returns_valid_weights() -> None:
    # Default loader (synthetic fixture in CI); just assert a valid, summed-to-1
    # sleeve-relative weight vector comes out.
    result = generate_signal(_PARAMS, date(2024, 9, 30))
    weights = result.weights_dict()
    assert weights
    assert sum(weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert all(0.0 <= w <= 1.0 for w in weights.values())
