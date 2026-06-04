"""B035 F003 — schemas for ``GET /api/market-context``.

Purely structured market-context payload (no AI text — B035 is a
non-AI data-display batch). One entry per catalogued series with its
latest value + date; ``latest_value`` / ``latest_date`` are nullable so
the Home card can render an empty state for a series not yet ingested.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MarketContextSeries(BaseModel):
    """Latest value for one market-context series."""

    series_id: str = Field(description="e.g. 'DGS10' / 'SPY'.")
    source: str = Field(description="'fred' / 'alpha_vantage'.")
    label: str = Field(description="Human-readable display label.")
    latest_value: float | None = Field(
        default=None, description="Latest observation value; null when none ingested."
    )
    latest_date: str | None = Field(
        default=None, description="ISO-8601 date of the latest observation, or null."
    )


class MarketContextResponse(BaseModel):
    """GET /api/market-context payload — one entry per catalogued series,
    in catalog order."""

    series: list[MarketContextSeries] = Field(default_factory=list)
