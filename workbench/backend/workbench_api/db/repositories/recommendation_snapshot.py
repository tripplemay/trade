"""B044 F002 — RecommendationSnapshotRepository.

Wraps the ``recommendation_snapshot`` table with the operations the daily
recommendations precompute (``workbench-recommendations`` timer) and the
``GET /api/recommendations/current`` read path need:

- :meth:`save_batch` — idempotent write of one as_of_date's full target set.
  Deletes any existing rows for that ``as_of_date`` then inserts the new batch,
  so a same-day re-run replaces rather than duplicates (the daily precompute
  recomputes "as of today" each run).
- :meth:`latest_snapshot` — all rows of the most recent ``as_of_date`` (the
  current target portfolio the request path maps to ``TargetPosition``).

The repository never imports ``trade`` or touches the network/disk — the
precompute job does the scoring and passes the rows in. That keeps the read
path self-contained (§12.10) and lets tests exercise the repo against
in-memory SQLite (mirrors B037 PriceSnapshotRepository).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import delete, select

from workbench_api.db.models.recommendation_snapshot import (
    DEFAULT_STRATEGY_ID,
    RecommendationSnapshot,
)
from workbench_api.db.repositories.base import Repository


class RecommendationSnapshotRepository(Repository[RecommendationSnapshot, UUID]):
    model = RecommendationSnapshot
    primary_key_attr = "id"

    def save_batch(
        self,
        *,
        as_of_date: date,
        rows: Sequence[dict[str, Any]],
        master_meta: dict[str, Any],
        computed_at: datetime | None = None,
        strategy_id: str = DEFAULT_STRATEGY_ID,
    ) -> list[RecommendationSnapshot]:
        """Replace the target set for ``(strategy_id, as_of_date)`` with ``rows``.

        Each row dict carries ``symbol`` / ``sleeve`` / ``target_weight`` and an
        optional ``rationale``. ``master_meta`` (planning_weights + data_source)
        is denormalised onto every row of the batch. Idempotent: an existing
        ``(strategy_id, as_of_date)`` set is deleted first, so a daily re-run
        overwrites cleanly. ``strategy_id`` defaults to Master (B057 backward
        compatibility); the delete is **scoped by strategy_id** so a regime
        run never tramples Master's rows for the same date. ``computed_at``
        defaults to now(UTC) and is overridable for tests.
        """

        # B053 F003 — guard against a future engine producing a portfolio that
        # does not sum to 100%. A non-empty target set's weights must sum to 1.0;
        # a gross miss (a dropped sleeve, a double-count, a missing normalise)
        # is a real bug we refuse to persist. Tolerance is 1e-3 — well above the
        # per-symbol 6-digit rounding the real precompute accumulates across the
        # ~20-40 symbol basket (≈1e-5 worst case), well below any structural
        # drift (≥1%). Empty batches (a valid "no targets" state) are skipped.
        if rows:
            weight_sum = sum(float(row["target_weight"]) for row in rows)
            if abs(weight_sum - 1.0) > 1e-3:
                raise ValueError(
                    f"recommendation target weights for {as_of_date} sum to "
                    f"{weight_sum:.6f}, not 1.0 (±1e-3) — refusing to persist a "
                    "portfolio that is not fully allocated (engine drift?)."
                )

        stamp = computed_at or datetime.now(UTC)
        self._session.execute(
            delete(RecommendationSnapshot).where(
                RecommendationSnapshot.as_of_date == as_of_date,
                RecommendationSnapshot.strategy_id == strategy_id,
            )
        )
        saved: list[RecommendationSnapshot] = []
        for row in rows:
            entry = RecommendationSnapshot(
                id=uuid4(),
                as_of_date=as_of_date,
                strategy_id=strategy_id,
                symbol=row["symbol"],
                sleeve=row["sleeve"],
                target_weight=float(row["target_weight"]),
                rationale=row.get("rationale"),
                computed_at=stamp,
                master_meta=master_meta,
            )
            self._session.add(entry)
            saved.append(entry)
        self._session.flush()
        return saved

    def latest_snapshot(
        self, strategy_id: str = DEFAULT_STRATEGY_ID
    ) -> list[RecommendationSnapshot]:
        """Return all rows of ``strategy_id``'s most recent ``as_of_date``.

        Scoped by ``strategy_id`` (default Master, B057 backward compatibility)
        so each mode resolves its own latest target independently — the max
        ``as_of_date`` is computed *within* the strategy, never across modes
        with different cadences. Empty list if the strategy has no rows.
        """

        latest_date = self._session.execute(
            select(RecommendationSnapshot.as_of_date)
            .where(RecommendationSnapshot.strategy_id == strategy_id)
            .order_by(RecommendationSnapshot.as_of_date.desc())
            .limit(1)
        ).scalar_one_or_none()
        if latest_date is None:
            return []
        stmt = (
            select(RecommendationSnapshot)
            .where(
                RecommendationSnapshot.as_of_date == latest_date,
                RecommendationSnapshot.strategy_id == strategy_id,
            )
            .order_by(RecommendationSnapshot.target_weight.desc())
        )
        return list(self._session.execute(stmt).scalars().all())

    def history_by_strategy(
        self, strategy_id: str, *, since: date | None = None
    ) -> list[RecommendationSnapshot]:
        """B080 F002 — all snapshot rows for ``strategy_id`` (optionally on/after
        ``since``), ordered by ``(as_of_date, symbol)``. Feeds the holdings-level
        rolling-IC calculator (the monitoring job reads the full daily history).
        Pure DB — uses the ``(strategy_id, as_of_date)`` index."""

        stmt = select(RecommendationSnapshot).where(
            RecommendationSnapshot.strategy_id == strategy_id
        )
        if since is not None:
            stmt = stmt.where(RecommendationSnapshot.as_of_date >= since)
        stmt = stmt.order_by(
            RecommendationSnapshot.as_of_date, RecommendationSnapshot.symbol
        )
        return list(self._session.execute(stmt).scalars().all())
