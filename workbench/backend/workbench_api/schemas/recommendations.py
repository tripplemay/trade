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
    has_mark: bool = Field(
        default=True,
        description=(
            "B053 F003 — False only when the symbol is HELD but has no market "
            "price, so current_weight=0 is an unpriced placeholder, not a real "
            "'not held'. The frontend shows a distinct '持有但无标价 / held, no "
            "price' label instead of a misleading 0%. True for priced holdings "
            "and for symbols the account does not hold (0% is then correct)."
        ),
    )


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


class ResearchCaveat(BaseModel):
    """B067 F003 — out-of-sample honesty disclosure surfaced from the latest
    snapshot's ``master_meta.research_caveat``.

    Populated **only** for research-state strategies that persist this block
    (the cn_attack momentum modes — see ``strategy_modes/cn_attack_precompute``
    ``CN_ATTACK_RESEARCH_CAVEAT``). ``None`` for funded / other modes whose
    ``master_meta`` carries no caveat, which is exactly how the frontend gates
    the disclosure (render only when this field is present).

    Every field is optional with a ``None`` default so the response is robust to
    older / partial snapshots and so future caveat keys never break validation
    (extra keys are ignored by Pydantic). The fields are honest disclosures, not
    computed values — the frontend renders them verbatim (B067 spec §0). The
    bilingual headline/detail pair lets the surface follow the active locale.
    """

    validated: bool | None = Field(
        default=None, description="False when the strategy is not out-of-sample validated."
    )
    oos_result: str | None = Field(
        default=None, description="Out-of-sample verdict, e.g. 'negative'."
    )
    oos_cagr_range: str | None = Field(
        default=None, description="Observed out-of-sample CAGR range, e.g. '-9% ~ -11%'."
    )
    headline_zh: str | None = Field(default=None, description="Chinese headline warning.")
    headline_en: str | None = Field(default=None, description="English headline warning.")
    detail_zh: str | None = Field(default=None, description="Chinese advisory-only detail.")
    detail_en: str | None = Field(default=None, description="English advisory-only detail.")
    backtest_ref: str | None = Field(
        default=None,
        description="Repo-relative path to the IS/OOS backtest record (B066 spec).",
    )


class RecommendationsResponse(BaseModel):
    """GET /api/recommendations/current payload."""

    as_of_date: str = Field(description="Signal date the recommendation was generated for.")
    target_positions: list[TargetPosition]
    gate_checks: list[GateCheck]
    wash_sale_flags: list[WashSaleFlag] = Field(default_factory=list)
    account_present: bool = Field(
        description="False when accounts/me.json is missing — the page renders an empty state."
    )
    research_caveat: ResearchCaveat | None = Field(
        default=None,
        description=(
            "B067 F003 — out-of-sample honesty disclosure from the latest snapshot's "
            "master_meta.research_caveat. None for funded / other modes that persist no "
            "caveat; the surface renders a prominent OOS disclosure only when present."
        ),
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
