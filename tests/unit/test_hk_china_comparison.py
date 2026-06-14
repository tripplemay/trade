"""B063 F003 — proxy-vs-real comparison harness.

Pins the quarterly metric math (same-caliber, applied identically to both
sides), the honest wipeout / edge handling, the bias-aware attribution
(point-in-time provenance incl. universe evolution + forced-defensive split,
residual-selection caveat, concentration top_n vs data-source), the cadence
guard, the end-to-end two-backtest run on one shared frame per side, and the
F004 report payload.
"""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest

from trade.backtest import hk_china as proxy_engine
from trade.backtest.hk_china_comparison import (
    ComparisonMetrics,
    _cagr,
    _metrics,
    build_comparison_payload,
    run_proxy_vs_real_comparison,
)
from trade.backtest.monthly import BacktestError, BacktestParameters, EquityPoint
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters

_AS_OF = date(2024, 6, 28)
_RISERS = ("3690.HK", "1810.HK", "9618.HK", "0939.HK", "0883.HK")
_BELLWETHERS = ("0700.HK", "9988.HK", "600519.SH")
_DEFENSIVE = "SGOV"


def _ramp(
    specs: dict[str, tuple[float, float]],
    *,
    as_of: date = _AS_OF,
    n_days: int = 460,
) -> pd.DataFrame:
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


class _FakeProxySignal:
    def __init__(self, weights: dict[str, float]) -> None:
        self._weights = weights
        self.parameters_hash = "fake-hash"

    def weights_dict(self) -> dict[str, float]:
        return self._weights

    def is_defensive(self) -> bool:
        return False


# --- metric math ---


def test_metrics_quarterly_annualization() -> None:
    ec = (
        EquityPoint(date(2023, 1, 1), 100_000.0),
        EquityPoint(date(2023, 4, 1), 110_000.0),
        EquityPoint(date(2023, 7, 1), 104_500.0),
    )
    m = _metrics(
        equity_curve=ec,
        starting_capital=100_000.0,
        ending_value=104_500.0,
        turnover=1.5,
        transaction_costs=20.0,
    )
    assert isinstance(m, ComparisonMetrics)
    assert m.n_periods == 2
    assert m.cagr == pytest.approx(1.045**2 - 1.0)  # (end/start)^(4/2) - 1
    assert m.max_drawdown == pytest.approx(-0.05)  # 104.5k off the 110k peak
    # returns [0.10, -0.05]; vol = stdev(ddof=1) * sqrt(4); sharpe = mean*4 / vol
    assert m.annualized_volatility == pytest.approx(0.2121320, rel=1e-5)
    assert m.sharpe == pytest.approx((0.025 * 4) / 0.2121320, rel=1e-5)
    assert m.turnover == 1.5
    assert m.transaction_costs == 20.0


def test_metrics_flat_curve_is_zero_not_nan() -> None:
    ec = (EquityPoint(date(2023, 1, 1), 100.0), EquityPoint(date(2023, 4, 1), 100.0))
    m = _metrics(
        equity_curve=ec,
        starting_capital=100.0,
        ending_value=100.0,
        turnover=0.0,
        transaction_costs=0.0,
    )
    assert m.cagr == pytest.approx(0.0)
    assert m.sharpe == 0.0
    assert m.annualized_volatility == 0.0
    assert m.max_drawdown == 0.0


def test_cagr_edge_cases_are_honest() -> None:
    # Wipeout (<=0 ending) → honest -100%, not a masking 0.0.
    assert _cagr(100_000.0, -500.0, 4) == pytest.approx(-1.0)
    assert _cagr(100_000.0, 0.0, 4) == pytest.approx(-1.0)
    # Degenerate inputs → 0.0 (no data / no periods), consistent with n_periods=0.
    assert _cagr(0.0, 100.0, 4) == 0.0
    assert _cagr(100.0, 100.0, 1) == 0.0  # single point → no period


# --- end-to-end comparison + bias attribution + payload ---


def _proxy_frame() -> pd.DataFrame:
    return _ramp({"MCHI": (40.0, 70.0), "FXI": (40.0, 60.0), _DEFENSIVE: (100.0, 100.0)})


def _real_frame() -> pd.DataFrame:
    specs = {t: (40.0, 40.0 + 10 * (i + 1)) for i, t in enumerate(_RISERS)}
    specs.update({t: (40.0, 60.0) for t in _BELLWETHERS})
    specs[_DEFENSIVE] = (100.0, 100.0)
    return _ramp(specs)


def _patch_proxy(monkeypatch: pytest.MonkeyPatch, weights: dict[str, float]) -> None:
    # The proxy signal is now pinned to the passed frame; the fake must accept the
    # injected ``prices`` kwarg (proving the threaded signature).
    monkeypatch.setattr(
        proxy_engine,
        "generate_hk_china_signal",
        lambda params, d, prices=None: _FakeProxySignal(weights),
    )


def test_run_comparison_produces_both_sides(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_proxy(monkeypatch, {"MCHI": 0.5, "FXI": 0.5})
    signal_dates = (date(2024, 6, 10), date(2024, 6, 20))
    result = run_proxy_vs_real_comparison(
        proxy_usd_prices=_proxy_frame(),
        real_usd_prices=_real_frame(),
        signal_dates=signal_dates,
        real_parameters=HkChinaRealParameters(top_n=3),
        backtest_parameters=BacktestParameters(starting_capital=100_000.0),
    )
    assert result.usd_caliber is True
    assert result.n_signal_dates == 2
    assert result.proxy.metrics.n_periods == 2
    assert result.real.metrics.n_periods == 2
    # Concentration framing: ETFs vs single names, parameter + realized.
    assert result.proxy.holding_kind == "diversified_etf"
    assert result.real.holding_kind == "single_name"
    assert result.proxy.selection_top_n == 2  # proxy default
    assert result.real.selection_top_n == 3
    assert result.proxy.avg_holdings == pytest.approx(2.0)  # MCHI + FXI
    assert result.real.avg_holdings == pytest.approx(3.0)  # top_n=3 risers
    # Point-in-time provenance.
    assert result.real.avg_scored is not None and result.real.avg_scored >= 5
    assert result.real.avg_candidates is not None and result.real.avg_candidates >= 8
    assert result.real.forced_defensive_periods == 0  # synthetic frame fully covers
    assert result.real.universe_size >= 20


def test_quarterly_cadence_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_proxy(monkeypatch, {"MCHI": 1.0})
    with pytest.raises(BacktestError, match="quarterly"):
        run_proxy_vs_real_comparison(
            proxy_usd_prices=_proxy_frame(),
            real_usd_prices=_real_frame(),
            signal_dates=(date(2024, 6, 10),),
            real_parameters=HkChinaRealParameters(rebalance_frequency="monthly"),
        )


def test_bias_notes_cover_honesty_requirements(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_proxy(monkeypatch, {"MCHI": 1.0})
    result = run_proxy_vs_real_comparison(
        proxy_usd_prices=_proxy_frame(),
        real_usd_prices=_real_frame(),
        signal_dates=(date(2024, 6, 10),),
    )
    joined = " ".join(result.bias_notes).lower()
    assert "point-in-time" in joined  # §2 PIT provenance
    assert "residual selection bias" in joined  # §2 residual / optimistic caveat
    assert "concentration" in joined  # §3 concentration vs data-source
    assert "top_n" in joined  # §3 concentration parameter surfaced
    assert "forced" in joined  # forced-defensive (data-gap) distinction surfaced
    assert "usd" in joined  # caliber statement
    assert len(result.bias_notes) == 4


def test_build_comparison_payload_has_deltas_and_notes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_proxy(monkeypatch, {"MCHI": 0.5, "FXI": 0.5})
    result = run_proxy_vs_real_comparison(
        proxy_usd_prices=_proxy_frame(),
        real_usd_prices=_real_frame(),
        signal_dates=(date(2024, 6, 10), date(2024, 6, 20)),
    )
    payload = build_comparison_payload(result)
    assert set(payload) >= {
        "usd_caliber",
        "proxy",
        "real",
        "deltas_real_minus_proxy",
        "bias_notes",
    }
    deltas = payload["deltas_real_minus_proxy"]
    assert isinstance(deltas, dict)
    assert set(deltas) >= {"cagr", "sharpe", "max_drawdown", "turnover"}
    assert isinstance(payload["bias_notes"], list)
    assert len(payload["bias_notes"]) == 4
    proxy_block = payload["proxy"]
    real_block = payload["real"]
    assert isinstance(proxy_block, dict)
    assert isinstance(real_block, dict)
    assert real_block["selection_top_n"] == 6  # real default surfaced in payload
    proxy_metrics = proxy_block["metrics"]
    real_metrics = real_block["metrics"]
    assert isinstance(proxy_metrics, dict)
    assert isinstance(real_metrics, dict)
    assert deltas["cagr"] == pytest.approx(real_metrics["cagr"] - proxy_metrics["cagr"])
