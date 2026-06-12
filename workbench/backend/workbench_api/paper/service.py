"""B056 F001 — paper-trading orchestration service.

Wires the pure engine (``engine.compute_rebalance``) to the repositories, the
strategy targets (``targets.load_strategy_targets``), and the price marks
(``services.prices_provider``). Two entrypoints:

* :func:`activate_paper_account` — create the virtual account with its initial
  capital and immediately build the first book from the strategy's current
  target (activation = the first rebalance from all cash).
* :func:`rebalance_if_due` — the daily MTM job (F002) calls this; it rebalances
  when the strategy publishes a *new* allocation (``target_key`` changed), so a
  stable within-quarter target never churns the book — and additionally retries
  a still-pending (degraded) build whose missing price marks have since arrived
  (B058 F001: a build that skipped symbols for want of marks stays
  ``build_complete=False`` and is rebuilt rather than stranded in cash).

Off the request path (job / CLI side): reads the already-stored strategy target
+ price marks, never imports ``trade`` or hits a broker (spec §4.3).
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.models.paper_account import PaperAccount, PaperPosition
from workbench_api.db.repositories.paper_account import (
    PaperAccountRepository,
    PaperPositionRepository,
    PaperRebalanceRepository,
)
from workbench_api.paper.engine import RebalancePlan, compute_rebalance
from workbench_api.paper.targets import StrategyTargets, load_strategy_targets
from workbench_api.services.mark_to_market import marks_for
from workbench_api.services.prices_provider import DbPriceProvider, PriceProvider

logger = logging.getLogger(__name__)

# Generator-chosen defaults (spec §4.2 / §8 left the values to the generator).
DEFAULT_INITIAL_CAPITAL = 100_000.0
DEFAULT_BASE_CURRENCY = "USD"
DEFAULT_FEE_BPS = 5.0
DEFAULT_SLIPPAGE_BPS = 5.0

# Equity at/below this is "nothing to invest" (matches engine._EPSILON).
_EPSILON = 1e-9


class PaperAccountExistsError(RuntimeError):
    """Raised when activating a strategy that already has a paper account."""


def _resolve_close_marks(
    provider: PriceProvider, symbols: set[str]
) -> dict[str, float]:
    """``SYMBOL -> latest_close`` over ``symbols`` (omits unmarkable symbols)."""

    marks = marks_for(provider, symbols)
    return {symbol: mark.latest_close for symbol, mark in marks.items()}


def _apply_rebalance(
    session: Session,
    account: PaperAccount,
    targets: StrategyTargets,
    *,
    on_date: date,
    now: datetime,
    provider: PriceProvider,
) -> RebalancePlan:
    """Compute + persist one rebalance: new book, cash, rebalance log row."""

    pos_repo = PaperPositionRepository(session)
    current = {
        p.symbol.upper(): (float(p.shares), float(p.avg_cost))
        for p in pos_repo.list_by_account(account.id)
    }
    symbols = set(current) | set(targets.weights)
    marks = _resolve_close_marks(provider, symbols)

    plan = compute_rebalance(
        cash=float(account.cash),
        current_positions=current,
        target_weights=targets.weights,
        marks=marks,
        fee_bps=float(account.fee_bps),
        slippage_bps=float(account.slippage_bps),
    )

    new_rows = [
        PaperPosition(
            id=uuid.uuid4().hex,
            account_id=account.id,
            symbol=p.symbol,
            shares=p.shares,
            avg_cost=p.avg_cost,
        )
        for p in plan.positions
    ]
    pos_repo.replace_positions(account.id, new_rows)

    # The target is FULLY built only when a trade actually happened AND no target
    # symbol was skipped for want of a usable price mark. A degraded build (a
    # no-op that built nothing, or a partial build that skipped symbols) leaves
    # ``build_complete`` False so the daily MTM job retries once the marks arrive
    # / equity is available — instead of the old bug, which committed
    # ``target_key`` unconditionally and stranded the account in cash forever
    # (B053 "impossible state never silent" family). Requiring ``traded`` means a
    # no-op (no marks / no equity) is never silently flagged complete while a
    # target weight sits unbuilt; the daily pending-guard then just no-ops it (no
    # churn) until it can genuinely be built.
    fully_built = plan.traded and not plan.skipped_symbols
    account.cash = plan.cash
    account.target_key = targets.target_key
    account.build_complete = fully_built
    if plan.traded:
        account.last_rebalanced_on = on_date
    account.updated_at = now
    PaperAccountRepository(session).upsert(account)

    if plan.traded:
        PaperRebalanceRepository(session).add(
            rebalance_id=uuid.uuid4().hex,
            account_id=account.id,
            rebalance_date=on_date,
            cost=plan.cost,
            target_key=targets.target_key,
            created_at=now,
        )
    if plan.skipped_symbols:
        logger.warning(
            "paper rebalance for strategy=%s reached target_key=%s only "
            "partially: %d target symbol(s) lacked a usable price mark and were "
            "not built (%s); build_complete=False, the daily job will retry once "
            "marks are available.",
            account.strategy_id,
            targets.target_key,
            len(plan.skipped_symbols),
            ",".join(plan.skipped_symbols),
        )
    return plan


def activate_paper_account(
    session: Session,
    *,
    strategy_id: str,
    on_date: date,
    now: datetime,
    initial_capital: float = DEFAULT_INITIAL_CAPITAL,
    base_currency: str = DEFAULT_BASE_CURRENCY,
    fee_bps: float = DEFAULT_FEE_BPS,
    slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
    provider: PriceProvider | None = None,
) -> tuple[PaperAccount, RebalancePlan | None]:
    """Create a paper account for ``strategy_id`` and build its first book.

    Returns ``(account, plan)``; ``plan`` is ``None`` when the strategy has no
    target yet (the account is created all-cash and will build on the first
    daily job that sees a target). Raises :class:`PaperAccountExistsError` if the
    strategy already has a paper account (one per strategy)."""

    acc_repo = PaperAccountRepository(session)
    if acc_repo.get_by_strategy(strategy_id) is not None:
        raise PaperAccountExistsError(strategy_id)

    account = PaperAccount(
        id=uuid.uuid4().hex,
        strategy_id=strategy_id,
        initial_capital=initial_capital,
        cash=initial_capital,
        base_currency=base_currency,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        activated_on=on_date,
        last_rebalanced_on=None,
        target_key=None,
        # Set explicitly (not relying on the column default) so the field-by-field
        # upsert always copies a concrete value — never writes NULL (B057 trap).
        build_complete=True,
        created_at=now,
        updated_at=now,
    )
    acc_repo.upsert(account)

    provider = provider or DbPriceProvider(session)
    targets = load_strategy_targets(session, strategy_id)
    if targets is None:
        return account, None
    plan = _apply_rebalance(
        session, account, targets, on_date=on_date, now=now, provider=provider
    )
    return account, plan


def _build_progress_available(
    session: Session,
    account: PaperAccount,
    targets: StrategyTargets,
    provider: PriceProvider,
) -> bool:
    """Whether retrying a *pending* (degraded) build can make progress now.

    A pending account (``build_complete`` False) skipped target symbols last time
    for want of a usable price mark. Retrying only helps once the WHOLE allocation
    is buildable — every target symbol has a usable mark AND there is equity to
    deploy. We deliberately do not chase partial coverage: a target symbol that
    is markable yet never lands as a held position (dust weight, or rounds to 0
    shares) would otherwise read as perpetual "progress" and force a rebalance
    every single day, churning the book and bleeding cost (spec §3: daily
    behaviour is cadence + drift, never a daily forced re-alignment). So the
    partial book is left to drift until it can be finished in one shot."""

    target_syms = {s.upper() for s, w in targets.weights.items() if w > 0}
    if not target_syms:
        return False  # nothing to build

    positions = PaperPositionRepository(session).list_by_account(account.id)
    symbols = {p.symbol.upper() for p in positions} | target_syms
    # Keep only *usable* marks (strictly positive close) — the SAME definition the
    # engine's ``_usable`` applies, so the guard's notion of "markable" cannot
    # diverge from what the engine will actually build. A zero/negative close is
    # a bad snapshot, not a buildable mark; treating it as covered would re-enter
    # the daily-churn bug this fix exists to kill (B058 F001 review).
    marks = {
        sym: close
        for sym, close in _resolve_close_marks(provider, symbols).items()
        if close > 0
    }

    # Equity actually investable now: cash + value of markable holdings. A
    # pending build that cannot be funded (e.g. a held name lost its mark and
    # cash is ~0) makes no progress — leave it alone, do not spin daily.
    equity = float(account.cash) + sum(
        float(p.shares) * marks[sym]
        for p in positions
        if (sym := p.symbol.upper()) in marks
    )
    if equity <= _EPSILON:
        return False
    return all(sym in marks for sym in target_syms)


def rebalance_if_due(
    session: Session,
    account: PaperAccount,
    *,
    on_date: date,
    now: datetime,
    provider: PriceProvider | None = None,
) -> RebalancePlan | None:
    """Rebalance ``account`` when the strategy published a new allocation, or
    finish a still-pending (degraded) build whose marks have since arrived.

    Returns the plan only when a real trade happened; ``None`` when the target is
    absent / unchanged and fully built / a pending build with no progress to make
    / a degraded no-op that traded nothing (the common daily case — MTM only, no
    churn, and the caller's ``rebalanced`` count means "the book actually
    traded")."""

    targets = load_strategy_targets(session, account.strategy_id)
    if targets is None:
        return None
    target_changed = targets.target_key != account.target_key
    if not target_changed and account.build_complete:
        return None  # stable, fully-built allocation → MTM only, no churn
    provider = provider or DbPriceProvider(session)
    # Same allocation but not fully built (pending retry): only rebalance when
    # the build can be finished now, else leave the partial book untouched.
    if not target_changed and not _build_progress_available(
        session, account, targets, provider
    ):
        return None
    plan = _apply_rebalance(
        session, account, targets, on_date=on_date, now=now, provider=provider
    )
    # A degraded no-op (nothing markable / no equity) updated the account state
    # but traded nothing — it is not a rebalance event.
    return plan if plan.traded else None
