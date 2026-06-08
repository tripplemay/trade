"""End-to-end signal pipeline for BL-B011-S2 HK-China Momentum.

Wires the HK-China Repository loaders → price-only factors → construction →
a :class:`SignalResult` recording the parameter hash + sleeve-relative target
weights, mirroring the B025 ``us_quality_momentum.signal`` shape so the Master
dispatch (F003) can call ``generate_signal(params, signal_date).weights_dict()``
exactly as it does for us_quality.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.data.hk_china_universe import load_prices, load_universe
from trade.strategies.hk_china_momentum.construction import (
    HkChinaPortfolio,
    build_portfolio,
)
from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters


@dataclass(frozen=True, slots=True)
class SignalResult:
    """All output recorded for a single ``as_of_date`` HK-China signal run."""

    as_of_date: date
    parameters_hash: str
    portfolio: HkChinaPortfolio

    def weights_dict(self) -> dict[str, float]:
        return self.portfolio.as_dict()

    def selected_tickers(self) -> tuple[str, ...]:
        return self.portfolio.selected

    def is_defensive(self) -> bool:
        """True when the sleeve went fully defensive (risk-off or no survivor)."""

        return not self.portfolio.selected


def generate_signal(
    parameters: HkChinaMomentumParameters,
    as_of_date: date,
    *,
    prices: pd.DataFrame | None = None,
) -> SignalResult:
    """Run the full pipeline at ``as_of_date`` and return a signed result.

    Uses the default loader source (unified real-data CSV when present, else
    the synthetic fixture). ``prices`` may be injected (already point-in-time
    safe) so deterministic tests / the Master backtest can pin a frame without
    a disk read."""

    universe = load_universe(as_of=as_of_date)
    universe_tickers = tuple(entry.ticker for entry in universe)
    frame = prices if prices is not None else load_prices(as_of=as_of_date)
    portfolio = build_portfolio(
        prices=frame,
        universe_tickers=universe_tickers,
        as_of=as_of_date,
        parameters=parameters,
    )
    return SignalResult(
        as_of_date=as_of_date,
        parameters_hash=parameters.parameter_hash(),
        portfolio=portfolio,
    )


__all__ = ["SignalResult", "generate_signal"]
