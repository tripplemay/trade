"""B063 F002 — end-to-end signal for the real-data HK-China research strategy.

Wires: point-in-time universe (listing_date <= as_of) → offline local-currency
prices → **USD conversion** (B063 F001 :class:`~trade.data.fx.FxConverter`,
as-of FX so no future rate leaks) → reused momentum/trend/regional-risk factors
→ generic top-N construction → a :class:`RealSignalResult` recording the
parameter hash, sleeve-relative USD target weights, and honesty provenance
(how many candidates had enough history to be scored).

Contract (deliberate, so look-ahead is impossible by construction):

* The injected ``prices`` (or the disk read) is **local-currency** OHLCV; the
  signal converts it to USD here, then runs the factors. Momentum is therefore
  FX-aware, same caliber as the US-listed proxy.
* Everything is filtered to ``date <= as_of`` (the factors re-filter too) and
  FX is taken as-of each bar's own date — no future data, ever.

Research-only: never wired into the Master or any live recommendation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from trade.data.fx import FxConverter
from trade.data.hk_china_real_universe import (
    load_real_prices,
    load_real_universe,
    to_usd_prices,
)
from trade.strategies.hk_china_real.construction import (
    RealPortfolio,
    build_real_portfolio,
)
from trade.strategies.hk_china_real.parameters import HkChinaRealParameters


@dataclass(frozen=True, slots=True)
class RealSignalResult:
    """All output recorded for a single ``as_of_date`` real-data HK-China run."""

    as_of_date: date
    parameters_hash: str
    portfolio: RealPortfolio

    def weights_dict(self) -> dict[str, float]:
        return self.portfolio.as_dict()

    def selected_tickers(self) -> tuple[str, ...]:
        return self.portfolio.selected

    def is_defensive(self) -> bool:
        """True when the sleeve went fully defensive (risk-off or no survivor)."""

        return not self.portfolio.selected


def generate_real_signal(
    parameters: HkChinaRealParameters,
    as_of_date: date,
    *,
    prices: pd.DataFrame | None = None,
    fx: FxConverter | None = None,
) -> RealSignalResult:
    """Run the full real-data pipeline at ``as_of_date`` and return a result.

    ``prices`` may be injected (already PIT-safe, **local currency**) so
    deterministic tests pin a frame without a disk read; otherwise the offline
    unified CSV is read (empty offline → degrades to fully defensive). ``fx``
    may be injected for deterministic conversion; otherwise the offline FX CSV
    is read."""

    universe = load_real_universe(as_of=as_of_date)
    universe_tickers = tuple(entry.ticker for entry in universe)

    local = prices if prices is not None else load_real_prices(as_of=as_of_date)
    converter = fx if fx is not None else FxConverter.load()
    usd_prices = to_usd_prices(local, converter)

    portfolio = build_real_portfolio(
        prices=usd_prices,
        universe_tickers=universe_tickers,
        as_of=as_of_date,
        parameters=parameters,
    )
    return RealSignalResult(
        as_of_date=as_of_date,
        parameters_hash=parameters.parameter_hash(),
        portfolio=portfolio,
    )


__all__ = ["RealSignalResult", "generate_real_signal"]
