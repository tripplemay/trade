"""Schemas for the recommendations endpoints (F010)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TargetPosition(BaseModel):
    """One target-weight entry in the recommended portfolio."""

    symbol: str
    target_weight: float = Field(ge=0.0, le=1.0)
    current_weight: float = Field(ge=0.0, le=1.0)
    diff: float = Field(description="target_weight - current_weight (can be negative).")
    rationale: str | None = None


class GateCheck(BaseModel):
    """One pre-trade gate evaluation surfaced in the gate panel."""

    name: str = Field(description="Gate identifier, e.g. 'kill_switch' / 'max_drawdown'.")
    status: str = Field(description="'pass' / 'warn' / 'fail'.")
    detail: str | None = None


class WashSaleFlag(BaseModel):
    """Heuristic flag: same symbol bought within 30 days surfaces a warning."""

    symbol: str
    last_buy_date: str = Field(description="ISO-8601 date of the prior buy.")
    days_since: int = Field(ge=0)


class RecommendationsResponse(BaseModel):
    """GET /api/recommendations/current payload."""

    as_of_date: str = Field(description="Signal date the recommendation was generated for.")
    target_positions: list[TargetPosition]
    gate_checks: list[GateCheck]
    wash_sale_flags: list[WashSaleFlag] = Field(default_factory=list)
    account_present: bool = Field(
        description="False when accounts/me.json is missing — the page renders an empty state."
    )


class SleeveNewsItem(BaseModel):
    """One sleeve-relevant news item (B034 F003).

    **Purely structured, no AI-generated text** — this is the B034
    non-generative boundary (spec §3): every field is metadata,
    deterministic topic tags, matched tickers, or a numeric relevance
    score. There is no free-form advice / summary field; generative
    advisory text is B036 scope. ``tests/safety/test_b034_no_generative_ai.py``
    pins this exact field set so a future free-text field can't slip in.
    """

    news_id: str = Field(description="News row UUID (string form).")
    title: str
    source: str = Field(description="'sec_edgar' / 'yahoo_rss'.")
    url: str = Field(description="Source URL (rendered as an external link).")
    published_at: str = Field(description="ISO-8601 publish timestamp.")
    content_sha256: str = Field(description="Snapshot body hash (B033 boundary p).")
    topics: list[str] = Field(
        default_factory=list,
        description="Deterministic topic tags (财报 / 重大事件 / …); never LLM-generated.",
    )
    matched_tickers: list[str] = Field(
        default_factory=list,
        description="Sleeve constituent tickers the news mentions (hard match).",
    )
    score: float = Field(description="Relevance score = matched-ticker count + cosine.")


class SleeveNewsResponse(BaseModel):
    """GET /api/recommendations/news payload — relevance-sorted news for
    one sleeve. Items are ordered most-relevant first."""

    items: list[SleeveNewsItem] = Field(default_factory=list)


class ExportTicketRequest(BaseModel):
    """POST /api/recommendations/export-ticket body."""

    as_of_date: str


class ExportTicketResponse(BaseModel):
    """POST /api/recommendations/export-ticket response."""

    path: str = Field(description="Repo-relative path of the written markdown checklist.")
    disclaimer: str = Field(
        description=(
            "Always 'research-only; this is a manual review checklist, "
            "not a trading instruction'."
        )
    )
