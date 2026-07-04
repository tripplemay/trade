"""B066 F002 — directional A-share transaction cost model.

A-share frictions are **asymmetric**: 印花税 (stamp duty) is levied on the *sell*
side only (0.1% as of 2023-08), while brokerage commission and slippage apply to
both sides. The US engine's single symmetric ``friction_rate`` cannot express
this, so the CN engine carries its own cost model rather than overloading the US
``BacktestConfig`` (US zero-regression).

All rates are in basis points (1 bp = 0.01%). Notionals are CNY amounts traded.
"""

from __future__ import annotations

from dataclasses import dataclass

# B081 F001 — 印花税 was halved 0.1%→0.05% on 2023-08-28 (口径更正; the backtest
# window crosses that date but the spec takes a single flat 5bp default, with the
# old 10bp口径 reproducible via an explicit CnCostModel(stamp_duty_bps=10.0) for the
# F004 A/B bit-level comparison). Commission + slippage unchanged.
DEFAULT_STAMP_DUTY_BPS = 5.0  # 0.05%, SELL side only (印花税, post-2023-08-28)
DEFAULT_COMMISSION_BPS = 2.5  # ~0.025%, both sides (佣金)
DEFAULT_SLIPPAGE_BPS = 5.0  # both sides


class CnCostError(ValueError):
    """Raised when a cost-model parameter is invalid."""


@dataclass(frozen=True, slots=True)
class CnCostModel:
    """Directional A-share cost model: stamp duty on sells only.

    ``buy_rate`` = commission + slippage; ``sell_rate`` = stamp duty + commission +
    slippage. So a round-trip pays the stamp duty exactly once (on the exit),
    matching real A-share execution.
    """

    stamp_duty_bps: float = DEFAULT_STAMP_DUTY_BPS
    commission_bps: float = DEFAULT_COMMISSION_BPS
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS

    def __post_init__(self) -> None:
        for name in ("stamp_duty_bps", "commission_bps", "slippage_bps"):
            if getattr(self, name) < 0:
                raise CnCostError(f"{name} must be >= 0")

    def buy_rate(self) -> float:
        """Fractional cost on a buy notional (no stamp duty)."""

        return (self.commission_bps + self.slippage_bps) / 10_000.0

    def sell_rate(self) -> float:
        """Fractional cost on a sell notional (includes stamp duty)."""

        return (self.stamp_duty_bps + self.commission_bps + self.slippage_bps) / 10_000.0

    def trade_cost(self, buy_notional: float, sell_notional: float) -> float:
        """Total cost for a trade with the given buy / sell CNY notionals.

        Buys and sells are costed at their own (different) rates — the asymmetry
        that makes the A-share model honest.
        """

        if buy_notional < 0 or sell_notional < 0:
            raise CnCostError("notionals must be >= 0")
        return buy_notional * self.buy_rate() + sell_notional * self.sell_rate()


__all__ = ["CnCostError", "CnCostModel"]
