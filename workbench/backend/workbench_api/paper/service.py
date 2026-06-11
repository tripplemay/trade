"""B056 F001 — paper-trading orchestration service.

Wires the pure engine (``engine.compute_rebalance``) to the repositories, the
strategy targets (``targets.load_strategy_targets``), and the price marks
(``services.prices_provider``). Two entrypoints:

* :func:`activate_paper_account` — create the virtual account with its initial
  capital and immediately build the first book from the strategy's current
  target (activation = the first rebalance from all cash).
* :func:`rebalance_if_due` — the daily MTM job (F002) calls this; it rebalances
  only when the strategy publishes a *new* allocation (``target_key`` changed),
  so a stable within-quarter target never churns the book.

Off the request path (job / CLI side): reads the already-stored strategy target
+ price marks, never imports ``trade`` or hits a broker (spec §4.3).
"""

from __future__ import annotations

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

# Generator-chosen defaults (spec §4.2 / §8 left the values to the generator).
DEFAULT_INITIAL_CAPITAL = 100_000.0
DEFAULT_BASE_CURRENCY = "USD"
DEFAULT_FEE_BPS = 5.0
DEFAULT_SLIPPAGE_BPS = 5.0


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

    account.cash = plan.cash
    account.target_key = targets.target_key
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


def rebalance_if_due(
    session: Session,
    account: PaperAccount,
    *,
    on_date: date,
    now: datetime,
    provider: PriceProvider | None = None,
) -> RebalancePlan | None:
    """Rebalance ``account`` iff the strategy published a new allocation.

    Returns the plan when a rebalance ran, ``None`` when the target is unchanged
    / absent (the common daily case — only MTM happens, no churn)."""

    targets = load_strategy_targets(session, account.strategy_id)
    if targets is None or targets.target_key == account.target_key:
        return None
    provider = provider or DbPriceProvider(session)
    return _apply_rebalance(
        session, account, targets, on_date=on_date, now=now, provider=provider
    )
