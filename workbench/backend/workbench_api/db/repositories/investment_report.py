"""B047 F004 — InvestmentReportRepository.

The canonical job writes investment reports here; the Reports request path
reads them (kind='investment'). Upsert is keyed by ``(strategy_id,
as_of_date)`` — one authoritative report per strategy per signal date.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.investment_report import (
    KIND_INVESTMENT,
    InvestmentReport,
)
from workbench_api.db.repositories.base import Repository


def _slug(strategy_id: str, as_of_date: date) -> str:
    return f"{strategy_id}-{as_of_date.isoformat()}"


class InvestmentReportRepository(Repository[InvestmentReport, UUID]):
    model = InvestmentReport
    primary_key_attr = "id"

    def upsert_report(
        self,
        *,
        strategy_id: str,
        as_of_date: date,
        title: str,
        markdown: str,
        metrics: dict[str, Any] | None,
        computed_at: datetime | None = None,
    ) -> InvestmentReport:
        """Insert or replace the report for ``(strategy_id, as_of_date)``."""

        stmt = select(InvestmentReport).where(
            InvestmentReport.strategy_id == strategy_id,
            InvestmentReport.as_of_date == as_of_date,
        )
        existing = self._session.execute(stmt).scalar_one_or_none()
        slug = _slug(strategy_id, as_of_date)
        stamp = computed_at or datetime.now(UTC)
        if existing is None:
            row = InvestmentReport(
                id=uuid4(),
                slug=slug,
                strategy_id=strategy_id,
                as_of_date=as_of_date,
                title=title,
                markdown=markdown,
                metrics_json=metrics,
                kind=KIND_INVESTMENT,
                computed_at=stamp,
            )
            self._session.add(row)
            self._session.flush()
            return row
        existing.slug = slug
        existing.title = title
        existing.markdown = markdown
        existing.metrics_json = metrics
        existing.kind = KIND_INVESTMENT
        existing.computed_at = stamp
        self._session.flush()
        return existing

    def list_reports(self) -> list[InvestmentReport]:
        """All investment reports, newest as_of_date first (then strategy_id)."""

        stmt = select(InvestmentReport).order_by(
            InvestmentReport.as_of_date.desc(), InvestmentReport.strategy_id
        )
        return list(self._session.execute(stmt).scalars().all())

    def get_by_slug(self, slug: str) -> InvestmentReport | None:
        stmt = select(InvestmentReport).where(InvestmentReport.slug == slug)
        return self._session.execute(stmt).scalar_one_or_none()
