"""B056 F003 — paper-trading read service (the 6-section page payload).

Assembles ``GET /api/paper/{strategy_id}`` from the paper tables + the live price
marks + the strategy's latest target. Self-contained per §12.10: reads only DB
tables (paper_*, recommendation_snapshot, price_snapshot) + the shared
mark-to-market / pnl helpers — never imports ``trade`` or reads a repo-root file.

All forward NAV / P&L values are REAL already-computed mark-to-market numbers
(positioning §1.1 — never a return prediction).
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from workbench_api.db.models.paper_account import PaperAccount, PaperPosition
from workbench_api.db.models.paper_nav_history import PaperNavHistory
from workbench_api.db.repositories.paper_account import (
    PaperAccountRepository,
    PaperNavHistoryRepository,
    PaperPositionRepository,
    PaperRebalanceRepository,
)
from workbench_api.paper.pnl import compute_position_pnl
from workbench_api.paper.targets import (
    PAPER_STRATEGIES,
    StrategyTargets,
    load_strategy_targets,
    paper_strategy_name,
)
from workbench_api.schemas.paper import (
    PaperDriftEntry,
    PaperNavPoint,
    PaperPositionPnl,
    PaperRebalanceEntry,
    PaperStrategiesResponse,
    PaperStrategy,
    PaperSummary,
    PaperView,
)
from workbench_api.services.mark_to_market import (
    MarkToMarket,
    compute_mark_to_market,
    marks_for,
)
from workbench_api.services.prices_provider import (
    DbPriceProvider,
    PriceMark,
    PriceProvider,
)

BENCHMARK_SYMBOL = "SPY"


def list_paper_strategies(session: Session) -> PaperStrategiesResponse:
    """The selectable strategies + whether each already has a paper account."""

    acc_repo = PaperAccountRepository(session)
    strategies = [
        PaperStrategy(
            strategy_id=sid,
            name=name,
            has_account=acc_repo.get_by_strategy(sid) is not None,
        )
        for sid, name in PAPER_STRATEGIES
    ]
    return PaperStrategiesResponse(strategies=strategies)


def _next_quarter_end(d: date) -> date:
    """Next quarter-end strictly after ``d`` (Master rebalance-day hint)."""

    ends = [date(d.year, 3, 31), date(d.year, 6, 30),
            date(d.year, 9, 30), date(d.year, 12, 31)]
    for end in ends:
        if end > d:
            return end
    return date(d.year + 1, 3, 31)


def build_paper_view(
    session: Session,
    strategy_id: str,
    *,
    provider: PriceProvider | None = None,
) -> PaperView:
    """Assemble the full page payload for ``strategy_id`` (inactive when no account)."""

    name = paper_strategy_name(strategy_id)
    account = PaperAccountRepository(session).get_by_strategy(strategy_id)
    if account is None:
        return PaperView(active=False, strategy_id=strategy_id, strategy_name=name)

    provider = provider or DbPriceProvider(session)
    positions = PaperPositionRepository(session).list_by_account(account.id)
    targets = load_strategy_targets(session, strategy_id)
    history = PaperNavHistoryRepository(session).list_by_account(account.id)

    symbols = {p.symbol.upper() for p in positions} | {BENCHMARK_SYMBOL}
    if targets is not None:
        symbols |= set(targets.weights)
    marks = marks_for(provider, symbols)
    close_marks = {sym: m.latest_close for sym, m in marks.items()}

    mtm = compute_mark_to_market(
        ((p.symbol, float(p.shares)) for p in positions), float(account.cash), marks
    )
    summary = _build_summary(account, mtm.nav, positions, marks, history)
    positions_out = _build_positions(positions, close_marks, mtm)
    nav_curve = _build_nav_curve(account, history)
    drift = _build_drift(mtm, targets)
    rebalances = _build_rebalances(session, account.id)

    return PaperView(
        active=True,
        strategy_id=strategy_id,
        strategy_name=name,
        summary=summary,
        cash=float(account.cash),
        nav_curve=nav_curve,
        positions=positions_out,
        drift=drift,
        rebalances=rebalances,
    )


def _build_summary(
    account: PaperAccount,
    current_nav: float,
    positions: list[PaperPosition],
    marks: dict[str, PriceMark],
    history: list[PaperNavHistory],
) -> PaperSummary:
    initial = float(account.initial_capital)
    total_pnl = current_nav - initial
    total_pnl_pct = (total_pnl / initial) if initial > 0 else 0.0

    # Today's P&L: Σ shares × (latest_close − prior_close) over marked holdings.
    today_pnl: float | None = None
    marked = [p for p in positions if p.symbol.upper() in marks]
    if marked:
        today_pnl = sum(
            float(p.shares)
            * (marks[p.symbol.upper()].latest_close - marks[p.symbol.upper()].prior_close)
            for p in marked
        )

    # SPY benchmark return since activation (first nav point's SPY close).
    activation_spy = next(
        (h.benchmark_close for h in history if h.benchmark_close), None
    )
    latest_spy = marks[BENCHMARK_SYMBOL].latest_close if BENCHMARK_SYMBOL in marks else None
    benchmark_pct: float | None = None
    if activation_spy and latest_spy:
        benchmark_pct = (latest_spy / activation_spy) - 1.0
    vs_benchmark = (
        total_pnl_pct - benchmark_pct if benchmark_pct is not None else None
    )

    ref_date = history[-1].as_of_date if history else account.activated_on
    days_running = max(0, (ref_date - account.activated_on).days)

    return PaperSummary(
        strategy_id=account.strategy_id,
        base_currency=account.base_currency,
        initial_capital=initial,
        activated_on=account.activated_on.isoformat(),
        days_running=days_running,
        current_nav=current_nav,
        total_pnl=total_pnl,
        total_pnl_pct=total_pnl_pct,
        today_pnl=today_pnl,
        benchmark_pnl_pct=benchmark_pct,
        vs_benchmark_pct=vs_benchmark,
        next_rebalance=_next_quarter_end(ref_date).isoformat(),
        fee_bps=float(account.fee_bps),
        slippage_bps=float(account.slippage_bps),
    )


def _build_positions(
    positions: list[PaperPosition],
    close_marks: dict[str, float],
    mtm: MarkToMarket,
) -> list[PaperPositionPnl]:
    pnl = compute_position_pnl(
        ((p.symbol, float(p.shares), float(p.avg_cost)) for p in positions),
        close_marks,
    )
    return [
        PaperPositionPnl(
            symbol=item.symbol,
            shares=item.shares,
            avg_cost=item.avg_cost,
            close=item.close,
            market_value=item.market_value,
            weight=mtm.current_weight(item.symbol),
            unrealized_pnl=item.unrealized_pnl,
            unrealized_pnl_pct=item.unrealized_pnl_pct,
        )
        for item in pnl
    ]


def _build_nav_curve(
    account: PaperAccount, history: list[PaperNavHistory]
) -> list[PaperNavPoint]:
    initial = float(account.initial_capital)
    activation_spy = next(
        (h.benchmark_close for h in history if h.benchmark_close), None
    )
    curve: list[PaperNavPoint] = []
    for h in history:
        benchmark_nav: float | None = None
        if activation_spy and h.benchmark_close:
            benchmark_nav = initial * (h.benchmark_close / activation_spy)
        curve.append(
            PaperNavPoint(
                date=h.as_of_date.isoformat(), nav=float(h.nav), benchmark_nav=benchmark_nav
            )
        )
    return curve


def _build_drift(
    mtm: MarkToMarket, targets: StrategyTargets | None
) -> list[PaperDriftEntry]:
    if targets is None:
        return []
    symbols = sorted(set(targets.weights) | set(mtm.by_symbol))
    drift: list[PaperDriftEntry] = []
    for symbol in symbols:
        current = mtm.current_weight(symbol)
        target = float(targets.weights.get(symbol, 0.0))
        drift.append(
            PaperDriftEntry(
                symbol=symbol,
                current_weight=current,
                target_weight=target,
                drift=current - target,
            )
        )
    return drift


def _build_rebalances(session: Session, account_id: str) -> list[PaperRebalanceEntry]:
    rows = PaperRebalanceRepository(session).list_by_account(account_id)  # newest-first
    # Cumulative cost across the oldest→newest order, mapped back onto each row.
    oldest_first = list(reversed(rows))
    cumulative = 0.0
    cum_by_id: dict[str, float] = {}
    for row in oldest_first:
        cumulative += float(row.cost)
        cum_by_id[row.id] = cumulative
    return [
        PaperRebalanceEntry(
            date=row.rebalance_date.isoformat(),
            cost=float(row.cost),
            cumulative_cost=cum_by_id[row.id],
        )
        for row in rows
    ]


def activate_view_account(
    session: Session,
    *,
    strategy_id: str,
    initial_capital: float,
    fee_bps: float,
    slippage_bps: float,
    on_date: date,
    now: datetime,
    provider: PriceProvider | None = None,
) -> tuple[PaperAccount, int]:
    """Activate via the F001 service; returns (account, positions_count)."""

    from workbench_api.paper.service import activate_paper_account

    account, plan = activate_paper_account(
        session,
        strategy_id=strategy_id,
        on_date=on_date,
        now=now,
        initial_capital=initial_capital,
        fee_bps=fee_bps,
        slippage_bps=slippage_bps,
        provider=provider,
    )
    return account, (len(plan.positions) if plan else 0)
