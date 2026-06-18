"""B066 F001 — end-to-end CN attack signal tests (injected synthetic A-share data).

The signal is exercised with injected ``prices`` / ``fundamentals`` /
``universe_members`` (the F002 daily-driver / test contract) so the engine is
covered without the VM's real A-share CSVs. The synthetic prices give each name a
distinct geometric growth → a known momentum ordering; one high-momentum name is
deliberately left without fundamentals to prove the quality filter (variant A
drops it, variant B keeps it).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    CnAttackParameters,
)
from trade.strategies.cn_attack_momentum_quality.signal import generate_cn_attack_signal

_AS_OF = date(2025, 6, 2)
_MEMBERS = ("600519.SH", "000858.SZ", "600036.SH", "300750.SZ", "002594.SZ")
# Daily growth → momentum ordering: 600519 > 000858 > 600036 > 300750 > 002594.
_GROWTH = {
    "600519.SH": 0.0015,
    "000858.SZ": 0.0012,
    "600036.SH": 0.0009,
    "300750.SZ": 0.0006,
    "002594.SZ": 0.0003,
}
# 600036.SH deliberately has NO fundamentals row → dropped by the quality filter.
_QUALITY_ROWS = {
    "600519.SH": dict(roe=0.05, gross_margin=0.20, fcf_yield=0.01, debt_to_assets=0.70),
    "000858.SZ": dict(roe=0.10, gross_margin=0.30, fcf_yield=0.02, debt_to_assets=0.60),
    "300750.SZ": dict(roe=0.20, gross_margin=0.50, fcf_yield=0.04, debt_to_assets=0.40),
    "002594.SZ": dict(roe=0.25, gross_margin=0.60, fcf_yield=0.05, debt_to_assets=0.30),
}


def _synth_prices() -> pd.DataFrame:
    days = pd.bdate_range("2024-04-01", "2025-06-02")
    rows: list[dict[str, object]] = []
    for ticker, growth in _GROWTH.items():
        for i, day in enumerate(days):
            price = 100.0 * (1.0 + growth) ** i
            rows.append(
                {
                    "date": day,
                    "ticker": ticker,
                    "open": price,
                    "high": price * 1.01,
                    "low": price * 0.99,
                    "close": price,
                    "adj_close": price,
                    "volume": 1_000_000,
                }
            )
    return pd.DataFrame(rows)


def _synth_fundamentals() -> pd.DataFrame:
    report_date = pd.Timestamp("2025-04-30")
    rows: list[dict[str, object]] = []
    for ticker, facts in _QUALITY_ROWS.items():
        rows.append(
            {
                "report_date": report_date,
                "ticker": ticker,
                "fiscal_quarter": "2025Q1",
                "fiscal_quarter_end": pd.Timestamp("2025-03-31"),
                "pe": 20.0,
                "pb": 3.0,
                "ev_ebitda": float("nan"),
                "earnings_yield": 0.05,
                **facts,
            }
        )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def prices() -> pd.DataFrame:
    return _synth_prices()


@pytest.fixture(scope="module")
def fundamentals() -> pd.DataFrame:
    return _synth_fundamentals()


def test_pure_momentum_selects_top_momentum_names(prices: pd.DataFrame) -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    result = generate_cn_attack_signal(
        params, _AS_OF, prices=prices, universe_members=_MEMBERS
    )
    assert result.universe_size == 5
    assert set(result.tickers()) == {"600519.SH", "000858.SZ", "600036.SH"}
    # equal-weight, cap (0.5) not binding → ~1/3 each.
    assert result.portfolio.total_invested() == pytest.approx(1.0, abs=1e-9)
    assert all(w == pytest.approx(1 / 3) for w in result.weights_dict().values())


def test_quality_filter_drops_name_without_fundamentals(
    prices: pd.DataFrame, fundamentals: pd.DataFrame
) -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
        top_n=3,
        max_position_weight=0.5,
        momentum_weight=0.5,
        quality_weight=0.5,
    )
    result = generate_cn_attack_signal(
        params,
        _AS_OF,
        prices=prices,
        fundamentals=fundamentals,
        universe_members=_MEMBERS,
    )
    # 600036.SH has no fundamentals row → the quality variant filters it out.
    assert "600036.SH" not in result.tickers()


def test_variants_pick_different_baskets(
    prices: pd.DataFrame, fundamentals: pd.DataFrame
) -> None:
    pure = generate_cn_attack_signal(
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
        ),
        _AS_OF,
        prices=prices,
        universe_members=_MEMBERS,
    )
    blended = generate_cn_attack_signal(
        CnAttackParameters(
            factor_variant=FACTOR_VARIANT_QUALITY_MOMENTUM,
            top_n=3,
            max_position_weight=0.5,
            momentum_weight=0.5,
            quality_weight=0.5,
        ),
        _AS_OF,
        prices=prices,
        fundamentals=fundamentals,
        universe_members=_MEMBERS,
    )
    assert set(pure.tickers()) != set(blended.tickers())


def test_factor_contributions_emitted_for_each_selection(prices: pd.DataFrame) -> None:
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    result = generate_cn_attack_signal(
        params, _AS_OF, prices=prices, universe_members=_MEMBERS
    )
    contributions = result.factor_contributions_dict()
    for ticker in result.tickers():
        assert ticker in contributions
        assert set(contributions[ticker]) == {"momentum"}


def test_records_parameters_hash_and_variant(prices: pd.DataFrame) -> None:
    params = CnAttackParameters(factor_variant=FACTOR_VARIANT_PURE_MOMENTUM)
    result = generate_cn_attack_signal(
        params, _AS_OF, prices=prices, universe_members=_MEMBERS
    )
    assert result.parameters_hash == params.parameter_hash()
    assert result.factor_variant == FACTOR_VARIANT_PURE_MOMENTUM


def test_empty_universe_returns_empty_portfolio(prices: pd.DataFrame) -> None:
    params = CnAttackParameters(factor_variant=FACTOR_VARIANT_PURE_MOMENTUM)
    result = generate_cn_attack_signal(
        params, _AS_OF, prices=prices, universe_members=()
    )
    assert result.universe_size == 0
    assert result.tickers() == ()
    assert result.portfolio.cash_buffer == pytest.approx(1.0)


def test_loads_universe_from_disk_when_not_injected(
    prices: pd.DataFrame, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Exercise the production default branch: universe_members omitted → the real
    # load_cn_universe(as_of) reads cn_pit_universe.csv from the VM data root
    # (WORKBENCH_DATA_ROOT), proving the loader wiring + PIT pass-through.
    universe_dir = tmp_path / "snapshots" / "universe"
    universe_dir.mkdir(parents=True)
    lines = ["as_of_date,ticker,rank,market_cap,avg_turnover,composite_score\n"]
    for rank, ticker in enumerate(_MEMBERS, start=1):
        lines.append(f"2025-03-31,{ticker},{rank},1.0e12,1.0e9,0.5\n")
    (universe_dir / "cn_pit_universe.csv").write_text("".join(lines), encoding="utf-8")
    monkeypatch.setenv("WORKBENCH_DATA_ROOT", str(tmp_path))

    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    # prices injected (no on-disk price file needed); universe loaded from disk.
    result = generate_cn_attack_signal(params, _AS_OF, prices=prices)
    assert result.universe_size == 5
    assert set(result.tickers()) == {"600519.SH", "000858.SZ", "600036.SH"}


def test_current_holdings_accepted_but_band_agnostic(prices: pd.DataFrame) -> None:
    # F001 contract: current_holdings is accepted (F002 daily-driver hook) but the
    # single-date signal computes the unconditional target regardless of it.
    params = CnAttackParameters(
        factor_variant=FACTOR_VARIANT_PURE_MOMENTUM, top_n=3, max_position_weight=0.5
    )
    without = generate_cn_attack_signal(
        params, _AS_OF, prices=prices, universe_members=_MEMBERS
    )
    with_holdings = generate_cn_attack_signal(
        params,
        _AS_OF,
        current_holdings={"002594.SZ": 0.5},
        prices=prices,
        universe_members=_MEMBERS,
    )
    assert without.weights_dict() == with_holdings.weights_dict()
