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
    # Per llm-provider-evaluation §5.2 — production tasks.
    # Model IDs use the dotted format the production aigc-gateway
    # exposes via ``GET /v1/models`` (verified 2026-05-27). F003 fix-
    # round 1 swapped the placeholder dashed IDs (e.g. ``claude-haiku-
    # 4-5``) for the live IDs.
    "daily_advisor": "claude-haiku-4.5",
    "quarterly_review": "claude-sonnet-4.6",
    "quarterly_review_deep": "claude-opus-4.7",
    "news_summarize": "gemini-3-flash",
    # B054 F-news — translate English news headlines to Simplified Chinese
    # (off the request path, no-AI boundary rule (e): translate only).
    # Routed to ByteDance Doubao-pro: a non-reasoning, Chinese-native model —
    # the cheapest IN PRACTICE for this task. The per-token-cheaper "flash"
    # models (qwen3.5-flash etc.) are reasoning models that burn thousands of
    # hidden thinking tokens on a one-line translation, so their billed output
    # ends up dearer than a non-reasoning model; doubao-pro returns just the
    # ~20-token translation (verified 2026-06-11: ~$0.000004/headline vs
    # ~$0.0003 on Haiku 4.5, ≈80× cheaper). The existing 1704 production
    # headlines were already backfilled on Haiku; this only changes FUTURE
    # daily-timer translations.
    "news_translate": "doubao-pro",
    "topic_tagging": "claude-haiku-4.5",
    "sharpe_tooltip": "claude-haiku-4.5",
    "robinhood_simplify": "claude-haiku-4.5",
    # B043 — grounded "why" explanation layer (Recommendations / Backtest / Risk).
    # Short grounded outputs, same tier as daily_advisor — Haiku 4.5 is plenty.
    "recommendation_rationale": "claude-haiku-4.5",
    "backtest_explanation": "claude-haiku-4.5",
    "risk_explanation": "claude-haiku-4.5",
    "embedding": "bge-m3",
    # B032 F001 — Sonnet 4.6 single-judge for the AI safety eval CI
    # gate. Per ai-safety-evals-2026-05.md §4: judge prompts need
    # cross-rule reasoning that Haiku/Flash do not reliably do; cost
    # stays bounded because the CI eval is 15 samples × ~2K tokens
    # × ~20 runs/month ≈ ¥30 (well under the ¥1500 monthly cap and
    # the 80% alert ratio).
    "safety_judge": "claude-sonnet-4.6",
    # B096 F001 — P4-F2 ADVISORY semantic judge (fuzzy-residual + grounding).
    # This is the LLM layer *above* the deterministic P4-F1 lint
    # (advisor/semantic_lint.py). It is advisory only (flags, never a deploy
    # gate), runs over a small labeled eval-set on committed cassettes, so
    # Haiku 4.5 is the right tier: cheap, and the two checks (Latin-residual
    # detection + does-this-number-trace-to-inputs) are short-context
    # classification, not the cross-rule reasoning the red-team safety_judge
    # needs. Distinct task (not a safety_judge reuse) so the advisory layer
    # can never be conflated with — or accidentally re-route — the hard gate.
    "semantic_judge": "claude-haiku-4.5",
    # Cost-guard fallback chain (callers re-route once the alert
    # threshold is crossed; per §6 keep the system functional).
    # bge-m3 is the only multilingual embedding the gateway currently
    # exposes, so the embedding fallback intentionally points at the
    # same model — the fallback semantics here are "stay functional",
    # not "downgrade tier".
    "_fallback_advisor": "claude-haiku-4.5",
    "_fallback_news": "gemini-3-flash",
    "_fallback_embedding": "bge-m3",
    # Offline CI placeholder — never selected by production callers,
    # but listed so the routing table is the single source of truth.
    "_ci_mock": "mock-provider",
}
"""Task → model name. Permanent boundary **(l)**: keep model names
only here, never in caller code. Adding a task = add a row + a
PRICE_TABLE entry below."""


PRICE_TABLE: Final[dict[str, tuple[float, float]]] = {
    # model_name → (input USD per 1M tokens, output USD per 1M tokens).
    # Sourced from production aigc-gateway ``GET /v1/models`` payload
    # (verified 2026-05-27). ±20% drift tolerated per spec §6; refine
    # with precise token counter later.
    "claude-haiku-4.5": (1.00, 5.00),
    "claude-sonnet-4.6": (3.00, 15.00),
    "claude-opus-4.7": (15.00, 75.00),
    "gemini-3-flash": (0.50, 3.00),
    # B054 F-news — ByteDance Doubao-pro (news_translate). Non-reasoning, so
    # the billed output is just the short translation. Live gateway price
    # 2026-06-11: $0.082192 in / $0.328767 out per 1M.
    "doubao-pro": (0.082192, 0.328767),
    "bge-m3": (0.084, 0.0),  # output_per_1m is 0 for embeddings
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
