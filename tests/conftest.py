"""B071 golden-fixture strategy harness — shared across tests/ subtrees.

Provides one deterministic way to run the dispatched backtest engines on the
committed golden real-data fixture (``data/fixtures/golden/``). Used by F003
(determinism + N-strategy pairwise-distinct, ``tests/unit/``) and F004 (the
permanent acceptance invariants, ``tests/acceptance/``). Living in the
``tests/`` root conftest makes the fixtures visible to both subtrees without a
fragile cross-module import.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = _REPO_ROOT / "data" / "fixtures" / "golden"

# Records-based engines include SGOV (real inception 2020-05-28). Start signals
# after SGOV has >12 months of history so the 12-1 momentum lookback is
# satisfied for every ranked symbol; the SGOV-less us_quality engine is run over
# the SAME window for a like-for-like "same period" comparison. The window still
# spans the 2022 bear market (the 2020 COVID crash sits in the price history the
# lookback consumes).
GOLDEN_SIGNAL_START = date(2021, 7, 1)
_AS_OF = date(2023, 12, 29)

# The strategies the golden fixture drives deterministically (a subset of the
# worker ``_DISPATCH`` table — the records-based engines + us_quality). cn_attack
# is excluded (A-share data not in golden, by design — see golden README).
GOLDEN_STRATEGY_NAMES = ("master", "momentum", "risk_parity", "hk_china", "us_quality")


def build_golden_strategy_results(start: date = GOLDEN_SIGNAL_START) -> dict[str, Any]:
    """Run the dispatched engines on the golden fixture over a common window.

    Returns ``{strategy_name: result}``. Pure engine path (no DB / no worker):
    builds the price records through the F003 ``fixture_dir`` seam, derives the
    quarterly / monthly signal dates, and runs each engine. Deterministic —
    same fixture + same window → bit-identical results.
    """

    import pandas as pd

    from trade.analysis.parameter_sweep import build_monthly_signal_dates
    from trade.backtest.hk_china import run_hk_china_quarterly_backtest
    from trade.backtest.master_portfolio import (
        identify_quarter_end_signal_dates,
        run_master_portfolio_quarterly_backtest,
    )
    from trade.backtest.monthly import run_multi_monthly_backtest
    from trade.backtest.risk_parity import run_risk_parity_monthly_backtest
    from trade.backtest.us_quality_momentum.engine import run_backtest as run_us_quality
    from trade.data.loader import load_prices

    tickers = sorted(
        pd.read_csv(GOLDEN_DIR / "prices_daily.csv", usecols=["ticker"])["ticker"].unique()
    )
    by_ticker = load_prices(tickers, _AS_OF, fixture_dir=GOLDEN_DIR)
    records = tuple(bar for bars in by_ticker.values() for bar in bars)
    all_dates = tuple(sorted({bar.date for bar in records}))
    last = all_dates[-1]
    # Drop the final trading date from the signal set (it has no T+1 open for
    # execution) and clamp the start to the lookback-safe window.
    quarter_sig = tuple(
        d for d in identify_quarter_end_signal_dates(all_dates) if start <= d < last
    )
    monthly_sig = tuple(
        d for d in build_monthly_signal_dates(all_dates, start, last) if d < last
    )

    return {
        "master": run_master_portfolio_quarterly_backtest(records, quarter_sig),
        "momentum": run_multi_monthly_backtest(records, monthly_sig),
        "risk_parity": run_risk_parity_monthly_backtest(records, monthly_sig),
        "hk_china": run_hk_china_quarterly_backtest(records, quarter_sig),
        "us_quality": run_us_quality(start=start, end=last, fixture_dir=GOLDEN_DIR),
    }


def golden_strategy_fingerprint(result: Any) -> tuple[float, int]:
    """Stable comparable signature of a backtest result: exact ending value +
    rebalance-period count. Bit-identical across reruns (determinism); differs
    across strategies (pairwise-distinct)."""

    periods = getattr(result, "rebalance_periods", None)
    if periods is None:
        periods = getattr(result, "rebalance_results", ())
    return (float(result.ending_value), len(periods))


@pytest.fixture(scope="session")
def golden_dir() -> Path:
    return GOLDEN_DIR


@pytest.fixture(scope="session")
def golden_strategy_names() -> tuple[str, ...]:
    return GOLDEN_STRATEGY_NAMES


@pytest.fixture(scope="session")
def golden_fingerprint() -> Any:
    """The fingerprint callable (conftest helpers aren't importable across the
    no-__init__ tests/ tree, so it is surfaced as a fixture)."""

    return golden_strategy_fingerprint


@pytest.fixture(scope="session")
def golden_strategy_builder() -> Any:
    """The build callable itself — lets determinism tests run it twice for an
    independent rerun comparison."""

    return build_golden_strategy_results


@pytest.fixture(scope="session")
def golden_strategy_results() -> dict[str, Any]:
    """The strategy results built once for the session (invariant assertions)."""

    return build_golden_strategy_results()
