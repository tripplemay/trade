"""B056 F001 — paper-trading (forward-simulation) models.

The paper-trading "forward bridge" between backtest (past) and real money
(forward, real): one **virtual** account per strategy that faithfully follows
the strategy's published target allocation, rebalances at the strategy's
rebalance points (close-price fills + real costs), and is marked to market
daily — so the user can watch the strategy's true out-of-sample forward
behaviour before / while trading real money. No broker, no real money.

Three tables:

* :class:`PaperAccount` — one row per ``strategy_id`` (Master first; B055 /
  future strategies plug into the SAME engine via the same target interface).
  Holds the virtual cash, the cost parameters, the activation date, and the
  ``target_key`` fingerprint of the allocation last applied (so the daily MTM
  job rebalances only when the strategy publishes a *new* allocation).
* :class:`PaperPosition` — the virtual holdings (``shares`` + ``avg_cost``).
* :class:`PaperRebalance` — one row per virtual rebalance event, recording
  only the **date + cost** (the simplified rebalance log the F003 page shows —
  the user confirmed "date + cost, not every fill" on 2026-06-11).

All money / share fields are ``Float`` to compose directly with the float
mark-to-market pipeline (``services/mark_to_market.py``); avg_cost is a plain
cost-basis average for the per-asset P&L display, never the books.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class PaperAccount(Base):
    __tablename__ = "paper_account"
    __table_args__ = (
        UniqueConstraint("strategy_id", name="uq_paper_account_strategy_id"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # The strategy this paper account forward-simulates (e.g.
    # "master_portfolio"). One paper account per strategy — the engine is
    # parameterized by this id so B055 / future strategies plug in unchanged.
    strategy_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    initial_capital: Mapped[float] = mapped_column(Float, nullable=False)
    cash: Mapped[float] = mapped_column(Float, nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    # Real cost model (the user chose "costs counted honestly"): commission +
    # slippage in basis points of traded notional, applied at each rebalance.
    fee_bps: Mapped[float] = mapped_column(Float, nullable=False)
    slippage_bps: Mapped[float] = mapped_column(Float, nullable=False)
    activated_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Last date a virtual rebalance ran (activation is the first), and the
    # fingerprint of the allocation then applied. The daily MTM job rebalances
    # only when the strategy's latest target_key differs from this — so a
    # stable within-quarter allocation does NOT churn the paper book.
    last_rebalanced_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"PaperAccount(id={self.id!r}, strategy_id={self.strategy_id!r}, "
            f"cash={self.cash!r})"
        )


class PaperPosition(Base):
    __tablename__ = "paper_position"
    __table_args__ = (
        UniqueConstraint("account_id", "symbol", name="uq_paper_position_account_symbol"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("paper_account.id"), nullable=False, index=True
    )
    symbol: Mapped[str] = mapped_column(String(16), nullable=False)
    shares: Mapped[float] = mapped_column(Float, nullable=False)
    avg_cost: Mapped[float] = mapped_column(Float, nullable=False)

    def __repr__(self) -> str:
        return (
            f"PaperPosition(account_id={self.account_id!r}, symbol={self.symbol!r}, "
            f"shares={self.shares!r})"
        )


class PaperRebalance(Base):
    __tablename__ = "paper_rebalance"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    account_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("paper_account.id"), nullable=False, index=True
    )
    rebalance_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Total real cost (commission + slippage) applied at this rebalance — the
    # only per-event datum the simplified F003 log shows.
    cost: Mapped[float] = mapped_column(Float, nullable=False)
    target_key: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"PaperRebalance(account_id={self.account_id!r}, "
            f"rebalance_date={self.rebalance_date!r}, cost={self.cost!r})"
        )
