"""B080 F003 — reverify enqueue/read service (request-path, no ``trade`` import).

The POST handler only validates the strategy + writes a ``queued`` row (deduped
against an in-flight queued job); the heavy fetch + backtest run on the worker. This
module must stay ``trade``-free so the request path stays self-contained (a safety
guard test asserts it).
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from workbench_api.db.models.reverify_job import ReverifyJob
from workbench_api.db.repositories.reverify_job import ReverifyJobRepository

# The research-state strategies a frozen re-validation may target (spec §2 F003).
REVERIFY_STRATEGIES = ("cn_attack_quality_momentum", "cn_attack_pure_momentum")


class UnknownStrategyError(ValueError):
    """Raised when an enqueue targets a strategy outside the reverify set."""


def enqueue_reverify(
    session: Session, *, strategy_id: str, as_of: date | None = None
) -> ReverifyJob:
    """Enqueue a re-validation job (or return the existing queued one — dedup)."""

    if strategy_id not in REVERIFY_STRATEGIES:
        raise UnknownStrategyError(strategy_id)
    repo = ReverifyJobRepository(session)
    existing = repo.latest_queued(strategy_id)
    if existing is not None:
        return existing
    return repo.enqueue(
        strategy_id=strategy_id, as_of=as_of.isoformat() if as_of else None
    )


def get_reverify_job(session: Session, job_id: str) -> ReverifyJob | None:
    return ReverifyJobRepository(session).get_by_id(job_id)
