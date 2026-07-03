"""B080 — monitoring surface schemas (F001 trial registry read model)."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class TrialRow(BaseModel):
    """One registered strategy trial (backfilled history or an auto-logged run)."""

    id: str
    batch: str
    strategy_id: str
    parameter_hash: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    universe: str | None = None
    window_start: date | None = None
    window_end: date | None = None
    oos_split: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    verdict: str = Field(description="GO / NO_GO / INCONCLUSIVE / NA.")
    source_ref: str
    notes: str | None = None


class TrialsResponse(BaseModel):
    """GET /api/monitoring/trials — the trial log + the per-strategy count that
    is the Deflated-Sharpe-Ratio denominator ``N`` (advisory/research only)."""

    trials: list[TrialRow]
    counts_by_strategy: dict[str, int] = Field(
        description="strategy_id → trial count (the DSR N per strategy)."
    )
    total: int
