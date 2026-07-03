"""B080 F001 — TrialRegistryRepository (structured trial log; DSR N source).

Pure DB. Supplies the two reads the monitoring surface + a future Deflated Sharpe
Ratio need — a per-strategy trial count (``N``) and the trial list — plus the two
writes: an idempotent ``upsert`` (the historical backfill keys on a deterministic
content id) and ``register`` (the backtest worker's auto-log of a completed run).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select

from workbench_api.db.models.trial_registry import TRIAL_VERDICTS, TrialRegistry
from workbench_api.db.repositories.base import Repository


class TrialRegistryRepository(Repository[TrialRegistry, str]):
    model = TrialRegistry
    primary_key_attr = "id"

    def count_by_strategy(self, strategy_id: str) -> int:
        """Number of registered trials for ``strategy_id`` — the DSR ``N``."""

        stmt = (
            select(func.count())
            .select_from(TrialRegistry)
            .where(TrialRegistry.strategy_id == strategy_id)
        )
        return int(self._session.execute(stmt).scalar_one())

    def counts_by_strategy(self) -> dict[str, int]:
        """``{strategy_id: trial_count}`` across the whole registry."""

        stmt = select(TrialRegistry.strategy_id, func.count()).group_by(
            TrialRegistry.strategy_id
        )
        return {sid: int(n) for sid, n in self._session.execute(stmt).all()}

    def list_by_strategy(self, strategy_id: str) -> list[TrialRegistry]:
        stmt = (
            select(TrialRegistry)
            .where(TrialRegistry.strategy_id == strategy_id)
            .order_by(TrialRegistry.created_at, TrialRegistry.id)
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_recent(self, limit: int = 200) -> list[TrialRegistry]:
        stmt = (
            select(TrialRegistry)
            .order_by(TrialRegistry.created_at.desc(), TrialRegistry.id)
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def register(
        self,
        *,
        id: str,
        batch: str,
        strategy_id: str,
        verdict: str,
        params: Mapping[str, Any] | None = None,
        metrics: Mapping[str, Any] | None = None,
        parameter_hash: str | None = None,
        universe: str | None = None,
        window_start: date | None = None,
        window_end: date | None = None,
        oos_split: str | None = None,
        source_ref: str = "",
        notes: str | None = None,
        created_at: datetime | None = None,
    ) -> TrialRegistry:
        """Insert / replace one trial row (upsert on ``id`` → idempotent backfill).

        ``verdict`` must be one of :data:`TRIAL_VERDICTS`. ``created_at`` defaults
        to now (UTC), overridable for deterministic seeds/tests.
        """

        if verdict not in TRIAL_VERDICTS:
            raise ValueError(f"invalid trial verdict {verdict!r} (want {TRIAL_VERDICTS})")
        return self.upsert(
            TrialRegistry(
                id=id,
                created_at=created_at or datetime.now(UTC),
                batch=batch,
                strategy_id=strategy_id,
                parameter_hash=parameter_hash,
                params=dict(params or {}),
                universe=universe,
                window_start=window_start,
                window_end=window_end,
                oos_split=oos_split,
                metrics=dict(metrics or {}),
                verdict=verdict,
                source_ref=source_ref,
                notes=notes,
            )
        )
