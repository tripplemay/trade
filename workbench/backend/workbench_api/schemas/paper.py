"""B056 F003 — schemas for the paper-trading (forward-simulation) page.

The ``GET /api/paper/{strategy_id}`` view backs all six page sections (spec §6):
summary, NAV curve (+ SPY overlay), per-asset P&L, allocation drift vs target,
the simplified rebalance log, and the settings/activation state. Pure structured
numbers — the forward NAV / P&L are REAL already-computed mark-to-market values
(no prediction). ``GET /api/paper/strategies`` lists the selectable strategies;
``POST /api/paper/activate`` starts a forward simulation.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaperStrategy(BaseModel):
    strategy_id: str
    name: str
    has_account: bool


class PaperStrategiesResponse(BaseModel):
    strategies: list[PaperStrategy] = Field(default_factory=list)


class PaperSummary(BaseModel):
    strategy_id: str
    base_currency: str
    initial_capital: float
    activated_on: str = Field(description="ISO activation date.")
    days_running: int
    current_nav: float
    total_pnl: float
    total_pnl_pct: float
    today_pnl: float | None = None
    benchmark_pnl_pct: float | None = Field(
        default=None, description="SPY return over the simulation period."
    )
    vs_benchmark_pct: float | None = Field(
        default=None, description="Account return minus SPY return (out/under-perf)."
    )
    next_rebalance: str | None = Field(
        default=None, description="ISO date hint of the strategy's next rebalance."
    )
    fee_bps: float
    slippage_bps: float
    # B080 F004 — the benchmark this book is measured against (SPY / CSI300), so the
    # panel labels the benchmark curve correctly (CN books note CSI300).
    benchmark_symbol: str = "SPY"
    # B080 F004 fix ③ — true when the book carries CN-data-caliber caveats: the
    # first-day fill used the activation-day available close, which given A-share data
    # latency may predate the activation day → a first-day NAV pricing artifact (not
    # real alpha); AND the benchmark switched SPY→CSI300 mid-history (older nav points
    # benchmark against SPY). Advisory annotation only — not recomputed. master → False.
    first_day_caveat: bool = False


class PaperNavPoint(BaseModel):
    date: str
    nav: float
    benchmark_nav: float | None = Field(
        default=None, description="SPY normalised to the account's initial capital."
    )


class PaperPositionPnl(BaseModel):
    symbol: str
    name: str | None = None  # B079 — display name; null → frontend shows raw code
    shares: float
    avg_cost: float
    close: float | None = None
    market_value: float | None = None
    weight: float
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None


class PaperDriftEntry(BaseModel):
    symbol: str
    name: str | None = None  # B079 — display name; null → frontend shows raw code
    current_weight: float
    target_weight: float
    drift: float = Field(description="current_weight - target_weight.")


class PaperRebalanceEntry(BaseModel):
    date: str
    cost: float
    cumulative_cost: float


class PaperView(BaseModel):
    """The full paper-trading page payload for one strategy."""

    active: bool = Field(description="False when this strategy has no paper account yet.")
    strategy_id: str
    strategy_name: str
    summary: PaperSummary | None = None
    cash: float = 0.0
    nav_curve: list[PaperNavPoint] = Field(default_factory=list)
    positions: list[PaperPositionPnl] = Field(default_factory=list)
    drift: list[PaperDriftEntry] = Field(default_factory=list)
    rebalances: list[PaperRebalanceEntry] = Field(default_factory=list)


class ActivatePaperRequest(BaseModel):
    strategy_id: str
    initial_capital: float = Field(default=100_000.0, gt=0)
    fee_bps: float = Field(default=5.0, ge=0)
    slippage_bps: float = Field(default=5.0, ge=0)


class ActivatePaperResponse(BaseModel):
    strategy_id: str
    activated: bool
    positions: int = 0


class RebalanceNowResponse(BaseModel):
    """B058 F004 — result of a manual "align to current target" rebalance.

    The frontend pairs this with the honest notice that this is a one-time manual
    alignment (daily behaviour stays cadence + drift). ``skipped_symbols`` lets it
    show "X 个目标缺市价未建仓" when a degraded build left part of the book in cash."""

    strategy_id: str
    has_target: bool = Field(
        description="False when the strategy has no target yet (refresh it first)."
    )
    rebalanced: bool = Field(description="True when a trade actually happened.")
    positions: int = Field(default=0, description="Holdings after the rebalance.")
    build_complete: bool = Field(
        description="True when every target symbol was built (no skips)."
    )
    skipped_symbols: list[str] = Field(
        default_factory=list,
        description="Target symbols not built for want of a usable price mark.",
    )
