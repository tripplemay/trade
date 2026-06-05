"""B036 F003 — advisor read service.

Assembles the ``GET /api/advisor`` payload from the latest precomputed
:class:`AdvisorRecommendation` per sleeve. Pure read over the DB + the
in-package sleeve list (``advisor_sleeves`` reads the strategy registry,
not a file) — no repo-root reads on the request path (v0.9.32 §12.10).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from workbench_api.advisor.precompute import advisor_sleeves
from workbench_api.db.repositories.advisor_recommendation import (
    AdvisorRecommendationRepository,
)
from workbench_api.schemas.advisor import (
    AdvisorReference,
    AdvisorResponse,
    AdvisorSleeveAdvice,
)


def get_advisor(session: Session) -> AdvisorResponse:
    """Return the latest advice per sleeve (sleeves with no result omitted)."""

    repo = AdvisorRecommendationRepository(session)
    sleeves: list[AdvisorSleeveAdvice] = []
    for sleeve in advisor_sleeves():
        latest = repo.latest_by_sleeve(sleeve)
        if latest is None:
            continue
        advice: dict[str, Any] = latest.advice_json or {}
        refs_raw: list[Any] = latest.references_json or []
        sleeves.append(
            AdvisorSleeveAdvice(
                sleeve=sleeve,
                advice=str(advice.get("advice", "")),
                rationale=str(advice.get("rationale", "")),
                references=[
                    AdvisorReference(
                        quant_signal_sha=str(r.get("quant_signal_sha", "")),
                        news_urls=[str(u) for u in r.get("news_urls", [])],
                    )
                    for r in refs_raw
                    if isinstance(r, dict)
                ],
                status=latest.status,
                generated_at=latest.generated_at.isoformat(),
            )
        )
    return AdvisorResponse(sleeves=sleeves)
