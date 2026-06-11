"""B056 F001 — repositories for the paper-trading tables.

Three thin repos over ``paper_account`` / ``paper_position`` / ``paper_rebalance``.
The virtual-rebalance engine (``workbench_api.paper.engine``) and the daily MTM
job (F002) compose them; the read path (F003 page service) reads them. None
import ``trade`` or touch the network — the engine receives the strategy targets
and price marks pre-resolved, keeping the read path self-contained (§12.10).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import delete, select

from workbench_api.db.models.paper_account import (
    PaperAccount,
    PaperPosition,
    PaperRebalance,
)
from workbench_api.db.models.paper_nav_history import PaperNavHistory
from workbench_api.db.repositories.base import Repository


class PaperAccountRepository(Repository[PaperAccount, str]):
    model = PaperAccount
    primary_key_attr = "id"

    def get_by_strategy(self, strategy_id: str) -> PaperAccount | None:
        stmt = select(PaperAccount).where(PaperAccount.strategy_id == strategy_id)
        return self._session.execute(stmt).scalar_one_or_none()

    def list_active(self) -> list[PaperAccount]:
        """All paper accounts (every account is an active forward simulation)."""

        stmt = select(PaperAccount).order_by(PaperAccount.strategy_id)
        return list(self._session.execute(stmt).scalars().all())


class PaperPositionRepository(Repository[PaperPosition, str]):
    model = PaperPosition
    primary_key_attr = "id"

    def list_by_account(self, account_id: str) -> list[PaperPosition]:
        stmt = (
            select(PaperPosition)
            .where(PaperPosition.account_id == account_id)
            .order_by(PaperPosition.symbol)
        )
        return list(self._session.execute(stmt).scalars().all())

    def replace_positions(
        self, account_id: str, positions: list[PaperPosition]
    ) -> None:
        """Atomically replace an account's holdings with ``positions``.

        The engine recomputes the full target book each rebalance, so a
        delete-then-insert is simpler and safer than per-symbol diffing of the
        ORM rows. A zero-share position is never persisted (the engine drops
        fully-sold symbols before calling this)."""

        self._session.execute(
            delete(PaperPosition).where(PaperPosition.account_id == account_id)
        )
        for pos in positions:
            self._session.add(pos)
        self._session.flush()


class PaperRebalanceRepository(Repository[PaperRebalance, str]):
    model = PaperRebalance
    primary_key_attr = "id"

    def add(
        self,
        *,
        rebalance_id: str,
        account_id: str,
        rebalance_date: date,
        cost: float,
        target_key: str,
        created_at: datetime,
    ) -> PaperRebalance:
        row = PaperRebalance(
            id=rebalance_id,
            account_id=account_id,
            rebalance_date=rebalance_date,
            cost=cost,
            target_key=target_key,
            created_at=created_at,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_by_account(self, account_id: str) -> list[PaperRebalance]:
        """Rebalance events newest-first (the simplified F003 log)."""

        stmt = (
            select(PaperRebalance)
            .where(PaperRebalance.account_id == account_id)
            .order_by(PaperRebalance.rebalance_date.desc())
        )
        return list(self._session.execute(stmt).scalars().all())


class PaperNavHistoryRepository(Repository[PaperNavHistory, str]):
    model = PaperNavHistory
    primary_key_attr = "id"

    def record_point(
        self,
        *,
        point_id: str,
        account_id: str,
        as_of_date: date,
        nav: float,
        cash: float,
        positions: list[dict[str, Any]],
        benchmark_close: float | None,
        created_at: datetime,
    ) -> PaperNavHistory:
        """Idempotent upsert of one daily MTM point.

        A same-day re-run overwrites the existing ``(account_id, as_of_date)``
        point rather than duplicating — the daily job is safe to re-run."""

        existing = self._session.execute(
            select(PaperNavHistory).where(
                PaperNavHistory.account_id == account_id,
                PaperNavHistory.as_of_date == as_of_date,
            )
        ).scalar_one_or_none()
        if existing is not None:
            existing.nav = nav
            existing.cash = cash
            existing.positions = positions
            existing.benchmark_close = benchmark_close
            existing.created_at = created_at
            self._session.flush()
            return existing
        row = PaperNavHistory(
            id=point_id,
            account_id=account_id,
            as_of_date=as_of_date,
            nav=nav,
            cash=cash,
            positions=positions,
            benchmark_close=benchmark_close,
            created_at=created_at,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_by_account(self, account_id: str) -> list[PaperNavHistory]:
        """All MTM points oldest-first (the forward NAV curve)."""

        stmt = (
            select(PaperNavHistory)
            .where(PaperNavHistory.account_id == account_id)
            .order_by(PaperNavHistory.as_of_date)
        )
        return list(self._session.execute(stmt).scalars().all())
