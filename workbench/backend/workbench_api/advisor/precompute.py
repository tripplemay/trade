"""B036 F002 — daily advisor precompute.

``run_daily`` generates one advisory result per sleeve and persists it,
idempotently by ``(sleeve, date)`` — a second run on the same day skips
sleeves already done (so a timer retry / manual re-run never duplicates
or re-bills the gateway).

Runs from the ``workbench-advisor`` systemd timer (boundary (r) as
revised in B036: a scheduler may run **CI-safety-gated** advisor
precompute — the red-team gate is a deploy gate, so by the time this runs
in production the advisor has already passed 100% block). It still never
touches a trade-execution surface; the advisor output is data written to
the DB, never an order.

cost guard: each ``advise_sleeve`` goes through ``gateway.advise`` which
runs the monthly budget guard (boundary (m)); a tripped cap raises and is
counted as an error rather than crashing the whole run.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy.orm import Session

from workbench_api.advisor.service import AdvisorService
from workbench_api.db.repositories.advisor_recommendation import (
    AdvisorRecommendationRepository,
)
from workbench_api.services.strategies import sleeve_strategies

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PrecomputeSummary:
    saved: int
    skipped: int
    errors: int


def advisor_sleeves() -> list[str]:
    """Distinct sleeves the advisor precomputes for — the strategy
    registry's sleeves (each has a derivable quant signal)."""

    return sorted({s.sleeve for s in sleeve_strategies()})


def run_daily(
    session: Session,
    advisor: AdvisorService,
    *,
    today: date | None = None,
) -> PrecomputeSummary:
    """Generate + persist advice per sleeve; idempotent by ``(sleeve, date)``."""

    run_date = today or datetime.now(UTC).date()
    repo = AdvisorRecommendationRepository(session)
    saved = 0
    skipped = 0
    errors = 0
    for sleeve in advisor_sleeves():
        latest = repo.latest_by_sleeve(sleeve)
        if latest is not None and latest.generated_at.date() == run_date:
            skipped += 1
            continue
        try:
            advisor.advise_sleeve(session, sleeve)
            # Commit per sleeve so this session does not hold the SQLite
            # write lock across the next sleeve. ``gateway.advise`` writes
            # llm_budget_log on a *separate* connection (the cost guard); a
            # single end-of-run commit kept this session's write transaction
            # open across sleeves, so the next cost-guard write deadlocked on
            # the WAL writer lock — 'database is locked' on the production VM
            # (2026-06-05, satellite_us_quality failed after risk_parity). WAL
            # + busy_timeout alone is not enough; the held transaction must be
            # released between sleeves.
            session.commit()
            saved += 1
        except Exception:
            session.rollback()
            errors += 1
            logger.exception("advisor_precompute_failure", extra={"sleeve": sleeve})
    return PrecomputeSummary(saved=saved, skipped=skipped, errors=errors)
