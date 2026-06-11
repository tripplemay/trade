"""B031 F001 — LLM routing table + cost estimation behaviour.

Pins the permanent boundary **(l)** contract: business code must
ask for a task name, never a model name. The tests assert the
routing table contains the §5.2 minimum task set, that unknown
tasks raise a fix-pointer error rather than silently falling back,
and that price-table coverage stays in sync with the routing
table (a forgotten PRICE_TABLE row would only surface as a
``KeyError`` in production cost estimation — better to fail here).
"""

from __future__ import annotations

import pytest

from workbench_api.llm.routing import (
    PRICE_TABLE,
    ROUTING_TABLE,
    estimate_cost_usd,
    route_task,
)

REQUIRED_PRODUCTION_TASKS: frozenset[str] = frozenset(
    {
        "daily_advisor",
        "quarterly_review",
        "quarterly_review_deep",
        "news_summarize",
        "topic_tagging",
        "sharpe_tooltip",
        "robinhood_simplify",
        "embedding",
    }
)
"""Tasks that must always exist in the routing table per
``docs/product/llm-provider-evaluation-2026-05.md`` §5.2."""


def test_route_task_returns_haiku_for_daily_advisor() -> None:
    assert route_task("daily_advisor") == "claude-haiku-4.5"


def test_route_task_returns_sonnet_for_quarterly_review() -> None:
    assert route_task("quarterly_review") == "claude-sonnet-4.6"


def test_route_task_returns_opus_for_quarterly_review_deep() -> None:
    """Deep escalation is reserved for the rare multi-sleeve composite
    review per §5.2 — the routing key must exist so a caller asking
    for the deep tier never silently downgrades to Sonnet."""

    assert route_task("quarterly_review_deep") == "claude-opus-4.7"


def test_route_task_returns_gemini_flash_for_news() -> None:
    assert route_task("news_summarize") == "gemini-3-flash"


def test_route_task_returns_doubao_for_news_translate() -> None:
    """B054 F-news: headline translation routes to the non-reasoning,
    Chinese-native doubao-pro — cheapest in practice (a reasoning 'flash'
    model would bill thousands of hidden thinking tokens per one-line
    translation). The model must have a PRICE_TABLE row."""

    assert route_task("news_translate") == "doubao-pro"
    assert "doubao-pro" in PRICE_TABLE


def test_routing_table_uses_production_gateway_model_ids() -> None:
    """F003 fix-round 1 regression: model IDs must match the production
    aigc-gateway catalogue (dotted format ``claude-haiku-4.5``, not
    the placeholder dashed ``claude-haiku-4-5`` shipped in F001).
    Catches a future drift back to the placeholder before it hits
    L2 acceptance."""

    expected_live_ids = {
        "claude-haiku-4.5",
        "claude-sonnet-4.6",
        "claude-opus-4.7",
        "gemini-3-flash",
        "bge-m3",
    }
    actual_ids = set(ROUTING_TABLE.values())
    missing = expected_live_ids - actual_ids
    assert missing == set(), (
        f"ROUTING_TABLE missing production gateway IDs: {sorted(missing)}. "
        "These IDs are what the live gateway returns from GET /v1/models — "
        "calling the gateway with a different ID raises 400 invalid_parameter."
    )


def test_route_task_unknown_raises_with_fix_pointer() -> None:
    """An unknown task must raise so a typo never silently falls back
    to a default model (permanent boundary **(l)**)."""

    with pytest.raises(RuntimeError) as exc_info:
        route_task("daily_advisour")  # cspell:ignore advisour — typo on purpose
    message = str(exc_info.value)
    assert "Unknown LLM task" in message
    assert "workbench_api/llm/routing.py" in message
    assert "ROUTING_TABLE" in message


def test_routing_table_covers_required_production_tasks() -> None:
    """Every task §5.2 calls out must exist. A future spec adding a
    new task widens this set explicitly."""

    missing = REQUIRED_PRODUCTION_TASKS - set(ROUTING_TABLE.keys())
    assert missing == set(), (
        f"ROUTING_TABLE missing required tasks: {sorted(missing)}. "
        "Add the entries before merging."
    )


def test_routing_table_models_all_have_price_entries() -> None:
    """Permanent invariant: every model the routing table can return
    must have a PRICE_TABLE row, otherwise the cost guard estimate
    raises ``KeyError`` mid-request in production."""

    referenced_models = set(ROUTING_TABLE.values())
    missing = referenced_models - set(PRICE_TABLE.keys())
    assert missing == set(), (
        f"PRICE_TABLE missing rows for: {sorted(missing)}. "
        "Add (input_usd_per_1m, output_usd_per_1m) entries."
    )


def test_estimate_cost_usd_uses_input_output_token_split() -> None:
    """Coarse cost calculation: 1M input tokens @ $1 + 1M output @ $5
    must total $6 for Haiku."""

    cost = estimate_cost_usd(
        "claude-haiku-4.5",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert cost == pytest.approx(6.0)


def test_estimate_cost_usd_is_zero_for_mock_provider() -> None:
    """Offline-CI provider must always report zero cost so unit tests
    that exercise the gateway never trigger budget warnings."""

    cost = estimate_cost_usd("mock-provider", input_tokens=10_000, output_tokens=10_000)
    assert cost == 0.0


def test_estimate_cost_usd_rounds_to_six_decimals() -> None:
    """Sub-cent precision keeps the budget log's float arithmetic
    stable across deletes / re-adds (B027 cost-guard pattern)."""

    cost = estimate_cost_usd(
        "gemini-3-flash", input_tokens=12_345, output_tokens=6_789
    )
    # gemini-3-flash priced at ($0.50, $3.00) per 1M tokens.
    # (12_345 / 1e6) * 0.50 + (6_789 / 1e6) * 3.00
    # = 0.0061725 + 0.020367 = 0.0265395 → rounds to 0.02654
    assert cost == pytest.approx(0.02654, abs=1e-5)
    # Result equals its own 6-decimal rounding (no tail noise).
    assert cost == round(cost, 6)


def test_routing_table_has_fallback_chain_entries() -> None:
    """§6 cost-guard downgrade chain: caller may re-route to
    ``_fallback_*`` once the alert threshold is crossed. Keep these
    routes present in the table so the fallback path never raises
    ``Unknown LLM task``."""

    for fallback in ("_fallback_advisor", "_fallback_news", "_fallback_embedding"):
        assert fallback in ROUTING_TABLE, f"missing fallback route: {fallback}"
        # Each fallback must itself point at a real model in the price table.
        assert ROUTING_TABLE[fallback] in PRICE_TABLE


def test_routing_table_has_ci_mock_entry() -> None:
    """Offline-CI placeholder. Listed in the table so the
    single-source-of-truth invariant holds even for synthetic test
    routes."""

    assert "_ci_mock" in ROUTING_TABLE
    assert ROUTING_TABLE["_ci_mock"] == "mock-provider"
