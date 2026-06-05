"""B036 F001 — AdvisorRecommendationRepository.

``save`` persists a generated advice row; ``latest_by_sleeve`` returns the
most recent row for a sleeve (newest ``generated_at`` first) — the
``GET /advisor`` route renders one latest result per sleeve.

Unlike the other repositories there is no ``save_if_new`` idempotency by a
natural key: each daily precompute is a fresh generation (a new
``generated_at``), so we always insert and read the newest. The F002
precompute keeps per-day idempotency at the job level instead.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from workbench_api.db.models.advisor_recommendation import AdvisorRecommendation
from workbench_api.db.repositories.base import Repository


class AdvisorRecommendationRepository(Repository[AdvisorRecommendation, UUID]):
    model = AdvisorRecommendation
    primary_key_attr = "id"

    def save(self, row: AdvisorRecommendation) -> AdvisorRecommendation:
        self._session.add(row)
        self._session.flush()
        return row

    def latest_by_sleeve(self, sleeve: str) -> AdvisorRecommendation | None:
        stmt = (
            select(AdvisorRecommendation)
            .where(AdvisorRecommendation.sleeve == sleeve)
            .order_by(AdvisorRecommendation.generated_at.desc())
            .limit(1)
        )
        return self._session.execute(stmt).scalar_one_or_none()
