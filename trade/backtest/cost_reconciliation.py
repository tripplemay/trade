"""B111 F004 — backtest-vs-paper cost caliber reconciliation.

**Fix-round update (evaluator finding B111-F006-1):** the two calibers are
now UNIFIED in code — see ``trade/backtest/execution_caliber.py``. Going
forward, the backtest engines and the paper engine share one cost formula
(``cost = capital x gross-turnover x (5bps fee + 5bps slippage)`` on BOTH
legs) and one execution-session rule (fills strictly after the signal
session; backtest at the T+1 open, paper at the first available close
strictly after the signal session).

This module keeps two things pure and testable:

1. **The PRE-unification gap** (provenance / re-calibration of historical
   verdicts): the legacy backtest caliber (3bps, one-sided buy-leg haircut)
   vs the paper caliber (10bps, both legs) — a 6.67x gap on a full swap.
   Historical "weakly positive" backtest verdicts must be re-scored at the
   unified caliber before being trusted (F004 deliverable #3).
2. **The POST-unification delta**: with both sides on the same formula the
   cost difference on any rebalance is 0 by construction (ratio 1.0). The
   remaining caliber difference is price REALISATION only — T+1 open
   (backtest) vs >=T+1 close (paper) — not a bps number and no longer a
   session mismatch.

It imports nothing from the workbench — the paper parameters are passed
in — so it stays a research-only reconciliation helper.
"""

from __future__ import annotations

from dataclasses import dataclass

from trade.backtest.execution_caliber import (
    LEGACY_BACKTEST_COST_BPS,
    LEGACY_BACKTEST_SLIPPAGE_BPS,
    LEGACY_PAPER_COST_BPS,
    LEGACY_PAPER_SLIPPAGE_BPS,
    UNIFIED_COST_BPS,
    UNIFIED_SLIPPAGE_BPS,
)

# The two PRE-unification calibers (kept for historical-artifact provenance;
# the values are pinned in execution_caliber so they cannot drift).
BACKTEST_COST_BPS = LEGACY_BACKTEST_COST_BPS
BACKTEST_SLIPPAGE_BPS = LEGACY_BACKTEST_SLIPPAGE_BPS
PAPER_FEE_BPS = LEGACY_PAPER_COST_BPS
PAPER_SLIPPAGE_BPS = LEGACY_PAPER_SLIPPAGE_BPS


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
    (``nav × turnover / 2``, the legacy ``monthly.py`` haircut).
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
    """Quantify the PRE-unification backtest-vs-paper cost gap for a rebalance.

    Defaults reflect the legacy shipped calibers: backtest 3bps one-sided vs
    paper 10bps both-legs. Returns the per-caliber cost, their difference,
    the ratio, and each expressed in bps of NAV so a historical verdict can
    be re-scored at the paper (now unified) caliber."""

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


def unified_rebalance_cost(nav: float, turnover: float) -> float:
    """Cost of one rebalance under the UNIFIED forward caliber.

    Both engines now compute exactly this: gross traded notional
    (``nav × turnover``, both legs) × (5bps fee + 5bps slippage). The
    post-unification backtest-vs-paper cost difference is therefore 0 on
    every rebalance (ratio 1.0) — the 6.67x gap existed only between the
    legacy calibers.
    """

    return rebalance_cost(
        nav,
        turnover,
        rate_bps=UNIFIED_COST_BPS + UNIFIED_SLIPPAGE_BPS,
        both_legs=True,
    )


def post_unification_comparison(
    nav: float, turnover: float
) -> CostCaliberComparison:
    """The backtest-vs-paper cost gap AFTER the unification landed.

    Both sides use the unified formula, so ``difference`` is 0 and ``ratio``
    is 1.0 for any positive turnover — the number the fix-round report
    tables against the pre-unification 6.67x.
    """

    return cost_caliber_comparison(
        nav,
        turnover,
        backtest_rate_bps=UNIFIED_COST_BPS + UNIFIED_SLIPPAGE_BPS,
        backtest_both_legs=True,
        paper_rate_bps=UNIFIED_COST_BPS + UNIFIED_SLIPPAGE_BPS,
        paper_both_legs=True,
    )
