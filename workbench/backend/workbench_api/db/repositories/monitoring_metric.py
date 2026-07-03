"""B080 F002 — MonitoringMetricRepository (L0 metric store; pure DB)."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select

from workbench_api.db.models.monitoring_metric import MonitoringMetric
from workbench_api.db.repositories.base import Repository


def _metric_id(strategy_id: str, as_of: date, metric: str) -> str:
    """Deterministic id on the (strategy_id, as_of, metric) unique key → the
    weekly re-run upserts in place."""

    key = f"{strategy_id}|{as_of.isoformat()}|{metric}".encode()
    return "mm-" + hashlib.sha256(key).hexdigest()[:20]


class MonitoringMetricRepository(Repository[MonitoringMetric, str]):
    model = MonitoringMetric
    primary_key_attr = "id"

    def upsert_metric(
        self,
        *,
        strategy_id: str,
        as_of: date,
        metric: str,
        value: float | None,
        meta: Mapping[str, Any] | None = None,
        computed_at: datetime | None = None,
    ) -> MonitoringMetric:
        """Insert / replace one metric row (idempotent on the natural key).

        ``value`` may be ``None`` for a partial / degraded metric — the ``meta``
        blob then carries the honesty flag (``partial`` / ``fidelity`` / etc.).
        """

        return self.upsert(
            MonitoringMetric(
                id=_metric_id(strategy_id, as_of, metric),
                strategy_id=strategy_id,
                as_of=as_of,
                metric=metric,
                value=value,
                meta=dict(meta or {}),
                computed_at=computed_at or datetime.now(UTC),
            )
        )

    def list_by_strategy(self, strategy_id: str) -> list[MonitoringMetric]:
        stmt = (
            select(MonitoringMetric)
            .where(MonitoringMetric.strategy_id == strategy_id)
            .order_by(MonitoringMetric.as_of, MonitoringMetric.metric)
        )
        return list(self._session.execute(stmt).scalars().all())

    def latest_by_metric(self, strategy_id: str) -> dict[str, MonitoringMetric]:
        """The most recent row per ``metric`` for ``strategy_id`` (panel read)."""

        latest: dict[str, MonitoringMetric] = {}
        for row in self.list_by_strategy(strategy_id):  # ascending as_of
            latest[row.metric] = row  # last write per metric wins
        return latest
