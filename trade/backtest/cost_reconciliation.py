"""B111 F004 — backtest-vs-paper cost caliber reconciliation.

The diagnosis (§1.4) showed the backtest is systematically OPTIMISTIC about
trading cost versus the paper book — three stacked mismatches:

1. **Rate:** the monthly backtest assumes ``1bp + 2bp = 3bps``
   (``trade/backtest/monthly.py`` ``BacktestParameters``); the paper engine
   charges ``5bps + 5bps = 10bps`` (``workbench_api/paper/service.py``).
2. **Sidedness:** ``monthly.py`` charges friction on the BUY leg only (one-sided
   haircut on deployed capital); the paper engine (and the master turnover model)
   charge the GROSS traded notional across BOTH legs.
3. **Fill timing:** the backtest fills at T+1 open (one session of lag / gap risk
   modelled); the paper book fills at the same-day close. This is a
   price-realisation caliber difference, NOT a bps number — noted, not scored.

This module turns (1) + (2) into a pure, testable NUMBER so historical verdicts
can be re-calibrated to the paper caliber (F004 deliverable #3). It imports
nothing from the workbench — the paper parameters are passed in — so it stays a
research-only reconciliation helper. It does NOT change any backtest or paper
cost (rewriting the backtest cost would rewrite validated history — H1); it only
quantifies the gap.
"""

from __future__ import annotations

from dataclasses import dataclass

# The two calibers as they ship today (the reconciliation defaults).
BACKTEST_COST_BPS = 1.0
BACKTEST_SLIPPAGE_BPS = 2.0
PAPER_FEE_BPS = 5.0
PAPER_SLIPPAGE_BPS = 5.0


@dataclass(frozen=True, slots=True)
class CostCaliberComparison:
    """The backtest-vs-paper cost gap on one rebalance of a given turnover."""

    nav: float
    turnover: float
    backtest_cost: float
    paper_cost: float
    difference: float
    ratio: float | None
    backtest_bps_of_nav: float
    paper_bps_of_nav: float


def rebalance_cost(
    nav: float, turnover: float, *, rate_bps: float, both_legs: bool
) -> float:
    """Cost of one rebalance under a (rate, sidedness) caliber.

    ``turnover`` is ``Σ |Δweight|`` (≈ 2.0 on a full swap = sell all + buy all).
    ``both_legs`` charges the full gross traded notional (``nav × turnover``, the
    paper / master-turnover model); one-sided charges only the buy leg
    (``nav × turnover / 2``, the ``monthly.py`` haircut).
    """

    if nav <= 0 or turnover <= 0:
        return 0.0
    traded = turnover if both_legs else turnover / 2.0
    return nav * traded * (rate_bps / 10_000.0)


def cost_caliber_comparison(
    nav: float,
    turnover: float,
    *,
    backtest_rate_bps: float = BACKTEST_COST_BPS + BACKTEST_SLIPPAGE_BPS,
    backtest_both_legs: bool = False,
    paper_rate_bps: float = PAPER_FEE_BPS + PAPER_SLIPPAGE_BPS,
    paper_both_legs: bool = True,
) -> CostCaliberComparison:
    """Quantify the backtest-vs-paper cost gap for a rebalance.

    Defaults reflect the shipped calibers: backtest 3bps one-sided vs paper
    10bps both-legs. Returns the per-caliber cost, their difference, the ratio,
    and each expressed in bps of NAV so a historical verdict can be re-scored at
    the paper caliber."""

    bt = rebalance_cost(
        nav, turnover, rate_bps=backtest_rate_bps, both_legs=backtest_both_legs
    )
    paper = rebalance_cost(
        nav, turnover, rate_bps=paper_rate_bps, both_legs=paper_both_legs
    )
    return CostCaliberComparison(
        nav=nav,
        turnover=turnover,
        backtest_cost=bt,
        paper_cost=paper,
        difference=paper - bt,
        ratio=(paper / bt if bt > 0 else None),
        backtest_bps_of_nav=(bt / nav * 10_000.0 if nav > 0 else 0.0),
        paper_bps_of_nav=(paper / nav * 10_000.0 if nav > 0 else 0.0),
    )
