"""B031 — LLM gateway module.

Provides ``LLMGateway`` (Stream 3.A starting point — Phase 2 first batch),
a vendor-neutral chat completion + embedding adapter that talks to
``aigc-gateway`` over HTTP REST (per
``docs/product/llm-provider-evaluation-2026-05.md`` §3.1 + §5.1).

The module is layered:

* :mod:`workbench_api.llm.routing` owns the task → model
  routing table and per-model price estimates. Business code never
  references model names directly — it asks the gateway for a task
  (e.g. ``"daily_advisor"``) and the routing table picks the model.
  This is permanent product boundary **(l)** from B031.
* :mod:`workbench_api.llm.gateway` owns the HTTP client + retry +
  schema parsing. Cost guard integration lands in B031 F002
  (``cost_guard.py``); F001 leaves a Protocol-shaped hook on the
  gateway constructor so the F002 ``MonthlyBudgetGuard`` can plug in
  without touching the gateway code.
"""

from workbench_api.llm.cost_guard import (
    USD_TO_CNY_RATE,
    BudgetExceeded,
    MonthlyBudgetGuard,
)
from workbench_api.llm.gateway import (
    AIGC_GATEWAY_BASE_URL,
    ChatRequest,
    ChatResult,
    LLMGateway,
)
from workbench_api.llm.routing import (
    PRICE_TABLE,
    ROUTING_TABLE,
    estimate_cost_usd,
    route_task,
)

__all__ = [
    "AIGC_GATEWAY_BASE_URL",
    "BudgetExceeded",
    "ChatRequest",
    "ChatResult",
    "LLMGateway",
    "MonthlyBudgetGuard",
    "PRICE_TABLE",
    "ROUTING_TABLE",
    "USD_TO_CNY_RATE",
    "estimate_cost_usd",
    "route_task",
]
