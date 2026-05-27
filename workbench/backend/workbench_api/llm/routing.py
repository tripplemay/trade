"""Task → model routing for the LLM gateway.

Permanent product boundary **(l)** (B031): business code MUST NOT
hardcode model names. Callers pass a task identifier (e.g.
``"daily_advisor"``) and the routing table picks the model. This
keeps a future model upgrade (e.g. Sonnet 4.6 → 4.8) a single-file
change inside ``ROUTING_TABLE`` rather than a search-and-replace
across the strategy / advisor surface.

The mapping mirrors ``docs/product/llm-provider-evaluation-2026-05.md``
§5.2 recommended routing:

* Daily / per-request advisor + simplification + tooltips → Haiku 4.5
  (cheapest tier, conversational quality plenty for short outputs)
* Quarterly portfolio review → Sonnet 4.6 (deeper reasoning, escalate
  to Opus 4.7 for the rare multi-sleeve composite call)
* News summarization → Gemini 2.0 Flash (long-context advantage on
  full-article ingestion; cheaper input tokens than Claude)
* Multilingual embedding → Cohere multilingual v3 (the
  English+中文 mix in this project's news corpus)

``_fallback_*`` entries are the cost-guard downgrade chain — when the
monthly cap is near the alert threshold the caller may explicitly
route to a fallback to keep the system functional while spend drops.
``_ci_mock`` is the offline-CI placeholder; pytest fixtures populate
it via monkeypatch.

PRICE_TABLE entries are USD per 1M tokens — only used to estimate
cost for the monthly cap (per spec, ±20% drift is acceptable in the
first version; precise token counting lands later).
"""

from __future__ import annotations

from typing import Final

ROUTING_TABLE: Final[dict[str, str]] = {
    # Per llm-provider-evaluation §5.2 — production tasks
    "daily_advisor": "claude-haiku-4-5",
    "quarterly_review": "claude-sonnet-4-6",
    "quarterly_review_deep": "claude-opus-4-7",
    "news_summarize": "gemini-2.0-flash",
    "topic_tagging": "claude-haiku-4-5",
    "sharpe_tooltip": "claude-haiku-4-5",
    "robinhood_simplify": "claude-haiku-4-5",
    "embedding": "cohere-embed-multilingual-v3",
    # Cost-guard fallback chain (callers re-route once the alert
    # threshold is crossed; per §6 keep the system functional).
    "_fallback_advisor": "claude-haiku-4-5",
    "_fallback_news": "gemini-2.0-flash",
    "_fallback_embedding": "gemini-text-embedding-004",
    # Offline CI placeholder — never selected by production callers,
    # but listed so the routing table is the single source of truth.
    "_ci_mock": "mock-provider",
}
"""Task → model name. Permanent boundary **(l)**: keep model names
only here, never in caller code. Adding a task = add a row + a
PRICE_TABLE entry below."""


PRICE_TABLE: Final[dict[str, tuple[float, float]]] = {
    # model_name → (input USD per 1M tokens, output USD per 1M tokens)
    # Sourced from public list-price tables as of 2026-05 (±20% drift
    # tolerated per spec §6; refine with precise token counter later).
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "cohere-embed-multilingual-v3": (0.10, 0.10),
    "gemini-text-embedding-004": (0.00, 0.00),  # free tier
    "mock-provider": (0.00, 0.00),  # CI mock
}
"""Per-model list-price reference for cost estimation. Keys must
cover every value in :data:`ROUTING_TABLE`."""


def route_task(task: str) -> str:
    """Return the model name configured for ``task``.

    Unknown task → ``RuntimeError`` with a fix pointer (adding a row
    to the routing table is the explicit, reviewed action — silently
    falling back would defeat permanent boundary **(l)**).
    """

    if task not in ROUTING_TABLE:
        raise RuntimeError(
            f"Unknown LLM task '{task}'. Add a row to "
            "workbench_api/llm/routing.py ROUTING_TABLE per "
            "docs/product/llm-provider-evaluation-2026-05.md §5.2, "
            "then add a matching PRICE_TABLE entry if it routes to a "
            "new model. Existing tasks: "
            f"{sorted(k for k in ROUTING_TABLE if not k.startswith('_'))}"
        )
    return ROUTING_TABLE[task]


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost of one call given input/output token counts.

    ``model`` must appear in :data:`PRICE_TABLE`; an unknown model
    raises ``KeyError`` so that adding a row to ``ROUTING_TABLE``
    without the matching price entry fails loudly at the first call
    rather than silently estimating zero.

    Cost is rounded to 6 decimals (sub-cent precision) to keep the
    budget-log arithmetic stable across float ops.
    """

    input_price, output_price = PRICE_TABLE[model]
    cost = (input_tokens / 1_000_000.0) * input_price + (
        output_tokens / 1_000_000.0
    ) * output_price
    return round(cost, 6)
