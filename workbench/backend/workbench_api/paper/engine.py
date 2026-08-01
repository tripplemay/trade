"""B056 F001 — pure virtual-rebalance engine.

``compute_rebalance`` is the heart of the paper-trading simulation and is
deliberately **pure**: cash + current positions + target weights + price marks
go in, the new book comes out. No ORM, no session, no network — so the tests
assert exact shares / cash / cost against known closes, and the same function
serves activation (first build from all cash) and every later rebalance.

Cost model (the user chose "costs counted honestly"): a rebalance trades a
gross notional ``Σ |Δshares_i| × close_i``; the real cost is
``gross × (fee_bps + slippage_bps) / 10_000`` and is deducted from cash. Fills
happen at the day's close (we measure the *strategy*, not the user's execution
quality — that is what the real journal measures, spec §1).

Why reserve cash for cost instead of investing full equity: a fully invested
target set (weights summing to 1.0) would leave nothing to pay the cost, driving
cash negative. The reservation must cover the FULL round-trip — a rebalance pays
cost on the SELLS as well as the buys (gross = |Σ Δshares| × close summed over
both legs). Reserving only the buy-side cost (``equity × (1 − cost_rate)``, the
pre-B078 formula) overdrew cash by ≈ the sell-side cost on a high-turnover
rebalance: cn_attack's monthly small-cap churn, fully invested after B074
stripped its CASH buffer, hit ``cash`` −102 / −103 in production (2026-06).
Additionally subtracting ``held_marked_value × cost_rate`` reserves the sell-side
cost (sells can never exceed the held value), so cash lands ≥ 0 at any turnover.
A from-cash build holds nothing (held value 0), so the formula collapses to
``equity × (1 − cost_rate)`` — activation is byte-identical (zero-regression).

B111-F006-3 (fix-round): the reservation assumes every planned sell executes.
When ``min_trade_fraction`` skips small SELLS, their proceeds never arrive and
a buy sized on the full-book premise overdraws cash (production Master paper:
cash $60.25 → −$18.94 on 2026-08-01). The engine therefore now decides all
trades first (min-trade included), then checks affordability against cash +
EXECUTED sell proceeds, and if the buys are not honestly fundable scales the
buy legs down proportionally (``buy_scale_factor``) — never clamping a
negative cash to 0, which would mask the overbuy. An explicit postcondition
raises if ``new_cash < -1e-6``.
"""

from __future__ import annotations

from dataclasses import dataclass

# Shares/cash below this are treated as zero (drop fully-sold positions; avoid
# persisting dust from float arithmetic).
_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class PlannedPosition:
    """One holding in the post-rebalance book."""

    symbol: str
    shares: float
    avg_cost: float


@dataclass(frozen=True, slots=True)
class RebalancePlan:
    """Result of one virtual rebalance (pure — caller persists it)."""

    cash: float
    positions: tuple[PlannedPosition, ...]
    cost: float
    traded_notional: float
    # Target symbols dropped because no usable (strictly-positive) price mark was
    # available (their weight falls to cash; surfaced so the caller logs the gap
    # honestly and the paper account stays build_complete=False to retry).
    skipped_symbols: tuple[str, ...]
    # True when any trade actually happened (equity>0 and at least one markable
    # target); False is a graceful no-op (no targets / no prices / no equity).
    traded: bool
    # B111-F006-3 — < 1.0 when the buy legs were scaled down to what cash +
    # executed sell proceeds honestly fund (skipped min-trade sells must not
    # fund buys). 1.0 = fully affordable, no scaling.
    buy_scale_factor: float = 1.0


def compute_rebalance(
    *,
    cash: float,
    current_positions: dict[str, tuple[float, float]],
    target_weights: dict[str, float],
    marks: dict[str, float],
    fee_bps: float,
    slippage_bps: float,
    min_trade_fraction: float = 0.0,
) -> RebalancePlan:
    """Compute the new book for one rebalance.

    ``current_positions`` maps ``SYMBOL -> (shares, avg_cost)``; ``marks`` maps
    ``SYMBOL -> latest_close``; ``target_weights`` maps ``SYMBOL -> weight``.
    All symbol keys are upper-cased by the caller. Returns a :class:`RebalancePlan`
    — never mutates its inputs.

    ``min_trade_fraction`` (B111 F004) is the minimum per-name trade size as a
    fraction of equity; a rebalance trade whose notional is below
    ``equity × min_trade_fraction`` is skipped, keeping that position at its
    current level, so the book stops churning ``$17``-dust orders on tiny drift
    (diagnosis §1.4/§6 F5). A full liquidation (the target dropped the name) is
    exempt so stale positions still close out. Defaults to ``0.0`` — no
    threshold — so activation and every existing caller are byte-identical."""

    cost_rate = (fee_bps + slippage_bps) / 10_000.0

    # A *usable* mark is a strictly positive close. A zero/negative close is a
    # bad price snapshot — treating it as a mark would build the target to 0
    # shares and silently strand its weight in cash (the S2 failure mode through
    # a different door), so it is treated exactly like a missing mark (B058 F001,
    # B053 "impossible state never silent" family).
    def _usable(symbol: str) -> float | None:
        close = marks.get(symbol)
        return close if close is not None and close > 0 else None

    # Equity = cash + market value of currently-held, markable positions. A held
    # symbol with no usable mark is kept untouched (cannot price → cannot trade),
    # and does not count toward equity (mirrors mark_to_market's degrade semantics).
    held_marked_value = 0.0
    for symbol, (shares, _avg) in current_positions.items():
        close = _usable(symbol)
        if close is not None:
            held_marked_value += shares * close
    equity = cash + held_marked_value

    # Markable targets only; a target with no usable mark is skipped (weight → cash).
    markable_targets = {
        symbol: weight
        for symbol, weight in target_weights.items()
        if weight > 0 and _usable(symbol) is not None
    }
    skipped = tuple(
        sorted(
            s for s, w in target_weights.items() if w > 0 and _usable(s) is None
        )
    )

    if equity <= _EPSILON or not markable_targets:
        # Graceful no-op: keep the existing book untouched.
        kept = tuple(
            PlannedPosition(sym, sh, avg)
            for sym, (sh, avg) in sorted(current_positions.items())
            if abs(sh) > _EPSILON
        )
        return RebalancePlan(
            cash=cash,
            positions=kept,
            cost=0.0,
            traded_notional=0.0,
            skipped_symbols=skipped,
            traded=False,
        )

    # B078 F002 — reserve cost for the FULL round-trip, not just the buy side.
    # ``equity × (1 − cost_rate)`` only covers the cost of buying ``investable``;
    # a rebalance also pays cost on the sells, so subtract ``held_marked_value ×
    # cost_rate`` (the sell-side bound — sells ≤ held value) so cash lands ≥ 0 on
    # any turnover. ``max(0.0, …)`` is defensive: an account already overdrawn by
    # the old bug (cash < 0 → equity < held value) self-heals by selling toward
    # all-cash rather than computing a negative target. From-cash builds (held
    # value 0) are unaffected — investable stays ``equity × (1 − cost_rate)``.
    investable = max(0.0, equity * (1.0 - cost_rate) - held_marked_value * cost_rate)

    # Desired shares per markable target.
    desired: dict[str, float] = {}
    for symbol, weight in markable_targets.items():
        close = marks[symbol]
        desired[symbol] = (weight * investable) / close if close > 0 else 0.0

    # Symbols touched = held (markable) ∪ target. Held-but-unmarkable stay put.
    touched = set(desired) | {
        s for s in current_positions if _usable(s) is not None
    }

    # B111 F004 — minimum per-name trade notional (0 → disabled). A rebalance
    # trade smaller than this is dust not worth the round-trip cost.
    min_trade_notional = equity * max(0.0, min_trade_fraction)

    gross_traded = 0.0
    cash_delta = 0.0
    new_positions: list[PlannedPosition] = []

    # Pass 1 — decide each touched symbol's post-trade shares (min-trade
    # filtering included) BEFORE any cash math, so the affordability check
    # below sees the trades that will ACTUALLY happen.
    planned_shares: dict[str, float] = {}
    for symbol in sorted(touched):
        old_shares, _old_avg = current_positions.get(symbol, (0.0, 0.0))
        new_shares = desired.get(symbol, 0.0)
        delta = new_shares - old_shares
        notional = abs(delta) * marks[symbol]
        # Skip a below-threshold trade: hold the position at its current level.
        # A full close (new_shares → 0) is exempt so stale names still exit.
        if (
            min_trade_notional > 0.0
            and 0.0 < notional < min_trade_notional
            and new_shares > _EPSILON
        ):
            new_shares = old_shares
        planned_shares[symbol] = new_shares

    # Pass 2 — cash-feasible sizing (B111-F006-3). The B078 reservation only
    # reserves COST; it implicitly assumes every planned sell executes. When
    # min-trade skips small SELLS, their proceeds never arrive, and a buy
    # sized on the full-book premise overdraws cash (production: Master paper
    # cash $60.25 → −$18.94 on 2026-08-01). A skipped sell must not fund a
    # buy — so when the executed trades are not affordable, scale the BUY
    # legs down proportionally to what cash + EXECUTED sell proceeds actually
    # cover. new_cash = cash + S − B − (S+B)·rate is feasible ⟺
    # B ≤ (cash + S·(1−rate)) / (1+rate); scaling buys by k = B_max/B lands
    # cash at ~0 by construction (never a clamp that would mask overbuying).
    sell_notional = 0.0
    buy_notional = 0.0
    for symbol, new_shares in planned_shares.items():
        old_shares, _old_avg = current_positions.get(symbol, (0.0, 0.0))
        delta = new_shares - old_shares
        if delta > _EPSILON:
            buy_notional += delta * marks[symbol]
        elif delta < -_EPSILON:
            sell_notional += -delta * marks[symbol]

    buy_scale_factor = 1.0
    max_affordable_buy = (cash + sell_notional * (1.0 - cost_rate)) / (1.0 + cost_rate)
    if buy_notional > _EPSILON and buy_notional > max_affordable_buy:
        buy_scale_factor = max(0.0, max_affordable_buy) / buy_notional
        for symbol in planned_shares:
            old_shares, _old_avg = current_positions.get(symbol, (0.0, 0.0))
            new_shares = planned_shares[symbol]
            if new_shares - old_shares > _EPSILON:
                # Partial fill: buys keep their target PROPORTIONS, just sized
                # to what is honestly fundable. No min-trade re-check here —
                # this is a forced partial fill, not a new dust order.
                planned_shares[symbol] = old_shares + (
                    new_shares - old_shares
                ) * buy_scale_factor

    # Pass 3 — build the book from the final per-symbol shares.
    for symbol in sorted(touched):
        close = marks[symbol]
        old_shares, old_avg = current_positions.get(symbol, (0.0, 0.0))
        new_shares = planned_shares[symbol]
        delta = new_shares - old_shares
        notional = abs(delta) * close
        gross_traded += notional
        cash_delta += -delta * close  # sells add cash, buys subtract
        if abs(new_shares) <= _EPSILON:
            continue  # fully sold — drop
        if delta > _EPSILON:
            # Buy (or new): blend the average cost.
            blended = (old_shares * old_avg + delta * close) / new_shares
            new_positions.append(PlannedPosition(symbol, new_shares, blended))
        else:
            # Sell / hold: cost basis per share is unchanged.
            avg = old_avg if old_avg > 0 else close
            new_positions.append(PlannedPosition(symbol, new_shares, avg))

    # Held-but-unmarkable positions are carried over untouched.
    for symbol, (shares, avg) in sorted(current_positions.items()):
        if _usable(symbol) is None and abs(shares) > _EPSILON:
            new_positions.append(PlannedPosition(symbol, shares, avg))

    cost = gross_traded * cost_rate
    new_cash = cash + cash_delta - cost
    # Explicit postcondition (B111-F006-3): cash may never go negative. Any
    # residual beyond float dust means the sizing above is broken — fail loud
    # rather than persist an impossible book (B053 family).
    if new_cash < -1e-6:
        raise RuntimeError(
            f"paper rebalance would overdraw cash: {new_cash:.6f} "
            f"(cash={cash}, sells={sell_notional:.2f}, buys={buy_notional:.2f}, "
            f"scale={buy_scale_factor:.6f}, cost={cost:.2f})"
        )
    new_cash = max(0.0, new_cash)  # float dust only (|x| ≤ 1e-6)

    return RebalancePlan(
        cash=new_cash,
        positions=tuple(sorted(new_positions, key=lambda p: p.symbol)),
        cost=cost,
        traded_notional=gross_traded,
        skipped_symbols=skipped,
        traded=True,
        buy_scale_factor=buy_scale_factor,
    )
