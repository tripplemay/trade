"""B043 F003 — RiskExplanationSnapshotRepository.

The daily risk-explanation precompute job upserts one row per ``as_of_date``;
the risk-panel request path reads the latest. Never imports ``trade`` / touches
the network — the job builds the grounding + calls the LLM and passes the result
in, keeping the read path self-contained (§12.10.2)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, select

from workbench_api.db.models.risk_explanation_snapshot import RiskExplanationSnapshot
from workbench_api.db.repositories.base import Repository


class RiskExplanationSnapshotRepository(Repository[RiskExplanationSnapshot, UUID]):
    model = RiskExplanationSnapshot
    primary_key_attr = "id"

    def upsert_explanation(
        self,
        *,
        as_of_date: date,
        master_dd: float,
        state: str,
        explanation: str | None,
        created_at: datetime | None = None,
    ) -> RiskExplanationSnapshot:
        """Replace the row for ``as_of_date`` (idempotent daily re-run)."""

        self._session.execute(
            delete(RiskExplanationSnapshot).where(
                RiskExplanationSnapshot.as_of_date == as_of_date
            )
        )
        row = RiskExplanationSnapshot(
            id=uuid4(),
            as_of_date=as_of_date,
            master_dd=master_dd,
            state=state,
            explanation=explanation,
            created_at=created_at or datetime.now(UTC),
        )
        self._session.add(row)
        self._session.flush()
        return row

    def latest(self) -> RiskExplanationSnapshot | None:
        """Return the most recent row, or ``None`` when none exists."""

        return self._session.execute(
            select(RiskExplanationSnapshot)
            .order_by(RiskExplanationSnapshot.as_of_date.desc())
            .limit(1)
        ).scalar_one_or_none()
