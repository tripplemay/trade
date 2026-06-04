"""B035 F003 — market-context read service.

Assembles the ``GET /api/market-context`` payload from the catalog +
``MarketContextRepository.latest_by_series``. Pure read over the
``market_context_observation`` table; **no repo-root file reads** on the
request path (labels come from the in-package
:data:`workbench_api.market.catalog.SERIES_CATALOG`) — v0.9.32 §12.10.
No AI text — every field is structured metadata or a number.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from workbench_api.db.repositories.market_context import MarketContextRepository
from workbench_api.market.catalog import SERIES_CATALOG
from workbench_api.schemas.market_context import (
    MarketContextResponse,
    MarketContextSeries,
)


def get_market_context(session: Session) -> MarketContextResponse:
    """Return the latest value per catalogued series, in catalog order.

    A series with no stored observation yet surfaces with ``latest_value``
    / ``latest_date`` = ``None`` (the Home card renders an empty cell)."""

    repo = MarketContextRepository(session)
    series: list[MarketContextSeries] = []
    for entry in SERIES_CATALOG:
        latest = repo.latest_by_series(entry.series_id)
        series.append(
            MarketContextSeries(
                series_id=entry.series_id,
                source=entry.source,
                label=entry.label,
                latest_value=float(latest.value) if latest is not None else None,
                latest_date=latest.obs_date.isoformat() if latest is not None else None,
            )
        )
    return MarketContextResponse(series=series)
