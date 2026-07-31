"""B111 F004 fix-round — the UNIFIED forward execution/cost caliber.

Single source of truth for the cost + execution assumptions every
forward-looking engine shares. Before this fix (evaluator finding
B111-F006-1) the repo shipped two divergent calibers:

* backtest side (``monthly.BacktestParameters``): 1bp cost + 2bp slippage,
  charged ONE-SIDED (buy-leg haircut on deployed capital), fills at T+1 open;
* paper side (``workbench_api.paper``): 5bps fee + 5bps slippage, charged on
  the gross traded notional of BOTH legs, fills at the signal session's close.

F004 round 1 quantified the gap (6.67x on a full swap) without closing it;
the evaluator ruled that a comparison function alone does not satisfy the
frozen acceptance ("paper 与回测统一执行/成本假设"). This module lands the
unification.

The unified forward caliber
---------------------------
1. **Rate** — 5bps commission + 5bps slippage **per leg**. This is the
   live-anchored rate: the production paper book's measured costs
   ($429.80 over 9 rebalances on ~$100k, avg turnover ~0.47) match the
   10bps both-legs model (~$47/rebalance), so unifying *down* to the old
   backtest rate would contradict live evidence.
2. **Sidedness** — cost is charged on the gross traded notional of BOTH
   legs (sell + buy), i.e. ``cost = capital x Sigma|delta_weight| x rate``.
   Every engine now uses this turnover form; the paper engine's
   ``gross_traded x rate`` is the same formula.
3. **Timing** — fills happen in a session STRICTLY AFTER the signal session
   (T+1 or later); same-session fills are banned. Backtests fill at the
   T+1 open (unchanged, the long-standing anti-lookahead convention). The
   paper engine fills at the first available close strictly after the
   signal session (>= T+1 close) — the price_snapshot table stores closes
   only, so T+1-open is not implementable on the paper side without a
   schema change; open-vs-close inside the T+1-or-later window is a
   price-realisation residual, no longer a session mismatch.

Provenance
----------
Historical artifacts produced before this fix keep the LEGACY caliber
labels below; they are not recomputed or re-labelled. The fixture-first MVP
workflow (``trade/config/defaults.py``) pins the legacy rate explicitly so
its frozen outputs stay byte-identical. Re-scoring a historical verdict at
the unified caliber is what ``trade/backtest/cost_reconciliation.py`` is
for.
"""

from __future__ import annotations

# ── Unified forward caliber ──────────────────────────────────────────────────
UNIFIED_COST_BPS = 5.0
UNIFIED_SLIPPAGE_BPS = 5.0
UNIFIED_COST_RATE = (UNIFIED_COST_BPS + UNIFIED_SLIPPAGE_BPS) / 10_000.0
# Both legs: the rate applies to the gross traded notional (sell + buy).
UNIFIED_COST_LEGS = 2
# Fills strictly after the signal session; backtest = T+1 open, paper = the
# first available close strictly after the signal session.
UNIFIED_EXECUTION_TIMING = "t_plus_1_session"
UNIFIED_BACKTEST_FILL = "t_plus_1_open"
UNIFIED_PAPER_FILL = "first_close_after_signal_session"

# ── Legacy calibers (provenance for pre-fix historical artifacts) ────────────
LEGACY_BACKTEST_COST_BPS = 1.0
LEGACY_BACKTEST_SLIPPAGE_BPS = 2.0
LEGACY_BACKTEST_ONE_SIDED = True  # monthly.py buy-leg haircut on deployed capital
LEGACY_PAPER_COST_BPS = 5.0
LEGACY_PAPER_SLIPPAGE_BPS = 5.0
LEGACY_PAPER_FILL_TIMING = "signal_session_close"
