"""B036 F003 — schemas for ``GET /api/advisor``.

The latest precomputed advisory result per sleeve. ``status`` is ``ok``
or ``insufficient_grounding`` — the Home card renders the
ai-safety §6.2 fallback for the latter and never inspects the advice
body. Every actionable ``ok`` item carries its citation set
(``quant_signal_sha`` + ``news_urls``) so the UI can render the required
references (boundary (d)).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdvisorReference(BaseModel):
    quant_signal_sha: str
    news_urls: list[str] = Field(default_factory=list)


class AdvisorSleeveAdvice(BaseModel):
    sleeve: str
    advice: str
    rationale: str
    references: list[AdvisorReference] = Field(default_factory=list)
    status: str = Field(description="'ok' / 'insufficient_grounding'.")
    generated_at: str = Field(description="ISO-8601 generation timestamp.")


class AdvisorResponse(BaseModel):
    """GET /api/advisor payload — latest advice per sleeve (sleeves with no
    precomputed result yet are omitted)."""

    sleeves: list[AdvisorSleeveAdvice] = Field(default_factory=list)
