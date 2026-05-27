"""LLM gateway — vendor-neutral chat completion + embedding adapter.

Backend talks to ``aigc-gateway`` over HTTP REST (per
``docs/product/llm-provider-evaluation-2026-05.md`` §3.1 + §5.1) so the
workbench never imports an Anthropic / OpenAI / Gemini SDK directly.
Provider-specific keys live inside aigc-gateway; the backend only
carries one secret, ``AIGC_GATEWAY_API_KEY``, plumbed through the
v0.9.30 §12.9 four-place wiring (``.env.example`` → settings →
``deploy.sh`` pre-flight → ``bootstrap-env.yml``).

Retry policy mirrors the Tiingo adapter (B027 F001):

* Up to 3 attempts on 5xx / 429 / connection-layer errors.
* Exponential backoff (0.5s × 2^n) capped at 8s.
* 4xx other than 429 fails fast — those are caller mistakes (bad
  model name, malformed messages) where retrying just burns budget.
* 401/403 surface as :class:`_AuthFailure` internally so
  ``health_check`` can return ``False`` cleanly.

Cost guard integration (permanent boundary **(m)** — ¥1500 monthly
cap) lands in B031 F002 via :class:`workbench_api.llm.cost_guard.MonthlyBudgetGuard`.
The gateway constructor accepts a ``guard`` Protocol so unit tests
can swap in a stub without standing up the budget-log DB; production
callers leave it ``None`` and get the real DB-backed default.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from workbench_api.llm.cost_guard import MonthlyBudgetGuard
from workbench_api.llm.routing import estimate_cost_usd, route_task

logger = logging.getLogger(__name__)


AIGC_GATEWAY_BASE_URL = "https://aigc.guangai.ai"
"""Default aigc-gateway REST base (production host). The gateway
exposes an OpenAI-compatible API surface — ``/v1/chat/completions``,
``/v1/embeddings``, ``/v1/models`` — so callers route requests to
the same paths the OpenAI SDK uses.

The constructor accepts a ``base_url`` override so unit tests can
point at a local stub without hitting the network, and a future
operator can run the workbench against a staging / self-hosted
gateway by passing a different URL through the service wiring.

History: B031 F001 shipped the placeholder ``aigc-gateway.example.com``;
Codex F003 first-round L2 caught the resulting ``Name or service not
known`` on the production VM. The fix-round 1 commit replaces the
default with the real production host."""

CHAT_ROUTE: str = "/v1/chat/completions"
"""OpenAI-compatible chat completion route."""

EMBED_ROUTE: str = "/v1/embeddings"
"""OpenAI-compatible embeddings route."""

HEALTH_ROUTE: str = "/v1/models"
"""Public unauthenticated models list — cheap reachability probe.
The gateway's ``GET /v1/models`` returns the catalog without any
billing impact, which is exactly the contract ``health_check()``
needs (spec F003 L2 §7: smoke must not increment ``llm_budget_log``)."""

DEFAULT_TIMEOUT_SECONDS: float = 60.0
MAX_RETRIES: int = 3
BACKOFF_BASE_SECONDS: float = 0.5
BACKOFF_CAP_SECONDS: float = 8.0


@dataclass(frozen=True, slots=True)
class ChatRequest:
    """Caller-facing chat request.

    ``task`` is the routing key (see
    :data:`workbench_api.llm.routing.ROUTING_TABLE`). Business code
    must never pass a model name — permanent boundary **(l)**.

    ``messages`` follows the standard ``[{"role": ..., "content": ...}, ...]``
    shape every modern chat completion API uses; the gateway forwards
    it verbatim so the caller doesn't need to know the underlying
    vendor's quirks.
    """

    task: str
    messages: list[dict[str, str]] = field(default_factory=list)
    max_tokens: int = 1024
    temperature: float = 0.7


@dataclass(frozen=True, slots=True)
class ChatResult:
    """Caller-facing chat result.

    ``model_used`` is what the gateway actually billed — usually the
    routed model, but a fallback path inside aigc-gateway may swap it
    (e.g. provider outage → secondary). Surfaced here so the caller's
    audit log records reality.

    ``aigc_log_id`` is the aigc-gateway internal log identifier; we
    record it on the workbench side so a future support ticket can
    correlate the local row to the gateway's request log without
    leaking message contents.
    """

    content: str
    model_used: str
    input_tokens: int
    output_tokens: int
    cost_usd_est: float
    aigc_log_id: str


class _HttpClient(Protocol):
    """Subset of :class:`httpx.Client` the gateway actually uses.

    Defined as a Protocol so unit tests can inject a hand-rolled stub
    (e.g. a scripted-response fake) without subclassing the heavy
    ``httpx.Client`` — that would drag its real connection-pool
    implementation into the offline test path.
    """

    def post(self, url: str, json: dict[str, Any]) -> Any: ...

    def get(self, url: str) -> Any: ...


class _Guard(Protocol):
    """Subset of the cost guard the gateway invokes.

    The default implementation is :class:`workbench_api.llm.cost_guard.MonthlyBudgetGuard`;
    unit tests typically inject a hand-rolled stub matching this
    Protocol so they can stay offline.
    """

    def check_and_increment(self, *, estimated_cost_usd: float) -> None: ...


class LLMGateway:
    """HTTP client for ``aigc-gateway``.

    Construct with an explicit ``api_key`` for unit tests; production
    callers leave it ``None`` and let the constructor resolve it from
    ``AIGC_GATEWAY_API_KEY`` in the process environment (populated by
    the systemd EnvironmentFile on the VM).

    ``base_url`` is overridable so a production URL change does not
    require editing this module. ``client`` / ``sleep`` / ``guard``
    are injectable for test isolation.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = AIGC_GATEWAY_BASE_URL,
        client: _HttpClient | None = None,
        sleep: Any = time.sleep,
        guard: _Guard | None = None,
    ) -> None:
        resolved_key = api_key or os.environ.get("AIGC_GATEWAY_API_KEY")
        if not resolved_key:
            raise RuntimeError(
                "AIGC_GATEWAY_API_KEY missing. Configure the GitHub repo "
                "secret AIGC_GATEWAY_API_KEY (Settings → Secrets and "
                "variables → Actions) so the bootstrap-env workflow can "
                "inject it into /etc/workbench/workbench.env via the "
                "systemd EnvironmentFile mechanism, or set "
                "AIGC_GATEWAY_API_KEY in your local shell for "
                "`python -m pytest` runs that exercise the real gateway "
                "path. Generate a backend-scoped key via the "
                "aigc-gateway dashboard or `mcp__aigc-gateway__create_api_key`."
            )
        self._api_key = resolved_key
        self._base_url = base_url.rstrip("/")
        self._client = client or httpx.Client(
            timeout=DEFAULT_TIMEOUT_SECONDS,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        )
        self._sleep = sleep
        # B031 F002: real cost guard is the production default.
        # ``MonthlyBudgetGuard.default()`` is cheap (frozen dataclass);
        # DB session opens only at ``check_and_increment`` time.
        self._guard = guard or MonthlyBudgetGuard.default()

    @property
    def api_key(self) -> str:
        """Resolved gateway API key. Exposed for diagnostics; never log."""

        return self._api_key

    @property
    def base_url(self) -> str:
        """Resolved gateway base URL (no trailing slash)."""

        return self._base_url

    def advise(self, request: ChatRequest) -> ChatResult:
        """High-level chat completion with task → model routing.

        Routing happens first (so an unknown task raises before any
        network spend), then the cost guard records the planned spend
        (a tripped cap raises and skips the HTTP call entirely),
        finally the gateway POSTs ``/chat`` and parses the result.
        """

        model = route_task(request.task)
        # Up-front cost estimate uses max_tokens as the output upper
        # bound — the actual output may be shorter, but the cap must
        # account for worst case so a runaway loop trips the guard
        # before billing reality. F001 leaves input_tokens at a coarse
        # estimate from message length; F002 may refine this once a
        # precise token counter ships.
        estimated_input_tokens = _estimate_input_tokens(request.messages)
        estimated_cost = estimate_cost_usd(
            model,
            input_tokens=estimated_input_tokens,
            output_tokens=request.max_tokens,
        )
        self._guard.check_and_increment(estimated_cost_usd=estimated_cost)

        payload: dict[str, Any] = {
            "model": model,
            "messages": list(request.messages),
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
        }
        response = self._post_with_retry(
            f"{self._base_url}{CHAT_ROUTE}", json=payload
        )
        return _parse_chat_result(response, fallback_model=model)

    def embed(self, texts: list[str], task: str = "embedding") -> list[list[float]]:
        """Return one vector per input text via the routed embedding model.

        ``task`` defaults to ``"embedding"`` (Cohere multilingual v3),
        but the routing table also exposes ``"_fallback_embedding"``
        for the free-tier downgrade path.
        """

        model = route_task(task)
        # Embeddings are billed per input token; output tokens are
        # not produced. Pass 0 for ``output_tokens`` so the estimate
        # reflects the actual cost shape.
        estimated_input_tokens = _estimate_input_tokens(
            [{"role": "user", "content": text} for text in texts]
        )
        estimated_cost = estimate_cost_usd(
            model,
            input_tokens=estimated_input_tokens,
            output_tokens=0,
        )
        self._guard.check_and_increment(estimated_cost_usd=estimated_cost)

        payload = {"model": model, "input": list(texts)}
        response = self._post_with_retry(
            f"{self._base_url}{EMBED_ROUTE}", json=payload
        )
        return _parse_embedding_vectors(response)

    def health_check(self) -> bool:
        """Probe ``GET /v1/models`` to confirm the gateway is reachable.

        ``/v1/models`` is the public, unauthenticated catalog endpoint
        — a 200 here proves DNS + TLS + nginx + gateway-process are
        all healthy without burning any per-request budget. The probe
        does not consult the cost guard (spec F003 L2 §7: smoke must
        not increment ``llm_budget_log``).

        Returns ``True`` for any 200 response, ``False`` when the
        gateway rejects the call as unauthorized (401/403; only
        relevant when a future gated probe endpoint is used). Other
        errors propagate so the operator can distinguish key-invalid
        from gateway-down at the call site.
        """

        try:
            self._get_with_retry(f"{self._base_url}{HEALTH_ROUTE}")
        except _AuthFailure:
            return False
        return True

    # --- internal HTTP helpers --------------------------------------------

    def _post_with_retry(self, url: str, *, json: dict[str, Any]) -> Any:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.post(url, json=json)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "aigc_gateway_network_retry",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                self._sleep_for_attempt(attempt)
                continue

            status = response.status_code
            if status == 200:
                return response.json()
            if status in (401, 403):
                raise _AuthFailure(
                    f"aigc-gateway auth failed ({status}); rotate "
                    "AIGC_GATEWAY_API_KEY"
                )
            if status == 429 or 500 <= status < 600:
                last_error = httpx.HTTPStatusError(
                    f"aigc-gateway {status}",
                    request=response.request,
                    response=response,
                )
                logger.warning(
                    "aigc_gateway_status_retry",
                    extra={
                        "url": url,
                        "status": status,
                        "attempt": attempt + 1,
                    },
                )
                self._sleep_for_attempt(attempt)
                continue
            response.raise_for_status()
        assert last_error is not None  # noqa: S101 — logic-protected branch
        logger.error(
            "aigc_gateway_retries_exhausted",
            extra={
                "url": url,
                "attempts": MAX_RETRIES,
                "error": str(last_error),
            },
        )
        raise last_error

    def _get_with_retry(self, url: str) -> Any:
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.get(url)
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "aigc_gateway_network_retry",
                    extra={"url": url, "attempt": attempt + 1, "error": str(exc)},
                )
                self._sleep_for_attempt(attempt)
                continue

            status = response.status_code
            if status == 200:
                return response.json()
            if status in (401, 403):
                raise _AuthFailure(
                    f"aigc-gateway auth failed ({status}); rotate "
                    "AIGC_GATEWAY_API_KEY"
                )
            if status == 429 or 500 <= status < 600:
                last_error = httpx.HTTPStatusError(
                    f"aigc-gateway {status}",
                    request=response.request,
                    response=response,
                )
                logger.warning(
                    "aigc_gateway_status_retry",
                    extra={"url": url, "status": status, "attempt": attempt + 1},
                )
                self._sleep_for_attempt(attempt)
                continue
            response.raise_for_status()
        assert last_error is not None  # noqa: S101 — logic-protected branch
        raise last_error

    def _sleep_for_attempt(self, attempt: int) -> None:
        delay = min(BACKOFF_BASE_SECONDS * (2**attempt), BACKOFF_CAP_SECONDS)
        self._sleep(delay)


class _AuthFailure(RuntimeError):
    """Internal sentinel for 401/403 from aigc-gateway.

    Kept private so the public surface stays a clean
    ``health_check() -> bool`` + ``advise``/``embed`` raising standard
    ``httpx`` errors on operator-actionable failures.
    """


def _estimate_input_tokens(messages: list[dict[str, str]]) -> int:
    """Coarse token count from message content character length.

    A reasonable industry approximation is ~4 chars per token for
    English-mixed text. The spec accepts ±20% drift in the first
    version (cost cap precision tightens once a real token counter
    lands). Returning at least 1 prevents zero-token requests from
    bypassing the cost guard entirely.
    """

    char_total = sum(len(str(m.get("content", ""))) for m in messages)
    return max(1, char_total // 4)


def _parse_chat_result(payload: Any, *, fallback_model: str) -> ChatResult:
    """Translate the aigc-gateway ``/v1/chat/completions`` JSON into
    :class:`ChatResult`.

    The gateway is OpenAI-compatible, so the response follows the
    OpenAI ``chat.completion`` envelope (verified against
    ``aigcgateway/src/app/api/v1/chat/completions/route.ts``):

    .. code-block:: json

        {
          "id": "chatcmpl-...",
          "object": "chat.completion",
          "model": "<routed model name>",
          "choices": [
            {"index": 0,
             "message": {"role": "assistant", "content": "..."},
             "finish_reason": "stop"}
          ],
          "usage": {"prompt_tokens": 12, "completion_tokens": 34,
                    "total_tokens": 46},
          "cost_usd_est": 0.001234  // optional, gateway-specific extension
        }

    The ``id`` field doubles as the aigc-gateway log identifier — we
    record it on the workbench side so a support ticket can correlate
    a local row to the gateway's request log without leaking the
    actual message content.

    Missing fields raise ``ValueError`` so a vendor schema drift fails
    loud rather than producing a silently-empty ``ChatResult``.
    """

    if not isinstance(payload, dict):
        raise ValueError(
            "aigc-gateway /v1/chat/completions returned non-dict payload "
            f"of type {type(payload).__name__}; cannot parse to ChatResult"
        )
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError(
            "aigc-gateway /v1/chat/completions payload missing non-empty "
            f"'choices' list; got keys {sorted(payload.keys())}"
        )
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError(
            "aigc-gateway /v1/chat/completions 'choices[0]' is not a dict; "
            f"got {type(first_choice).__name__}"
        )
    message = first_choice.get("message")
    if not isinstance(message, dict) or "content" not in message:
        raise ValueError(
            "aigc-gateway /v1/chat/completions 'choices[0].message.content' "
            f"missing; got message={message!r}"
        )
    usage = payload.get("usage") or {}
    input_tokens = int(usage.get("prompt_tokens", 0))
    output_tokens = int(usage.get("completion_tokens", 0))
    return ChatResult(
        content=str(message["content"]),
        model_used=str(payload.get("model") or fallback_model),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd_est=float(payload.get("cost_usd_est", 0.0)),
        aigc_log_id=str(payload.get("id", "")),
    )


def _parse_embedding_vectors(payload: Any) -> list[list[float]]:
    """Translate the aigc-gateway ``/v1/embeddings`` JSON into vector
    lists.

    OpenAI-compatible envelope::

        {
          "object": "list",
          "data": [
            {"object": "embedding", "embedding": [...], "index": 0},
            ...
          ],
          "model": "bge-m3",
          "usage": {"prompt_tokens": 12, "total_tokens": 12}
        }

    Malformed payloads raise ``ValueError`` so a vendor schema drift
    fails ingest immediately rather than writing zero-length vectors
    into a downstream RAG index.
    """

    if not isinstance(payload, dict) or "data" not in payload:
        raise ValueError(
            "aigc-gateway /v1/embeddings payload missing 'data'; got "
            f"{type(payload).__name__}"
        )
    data = payload["data"]
    if not isinstance(data, list):
        raise ValueError(
            "aigc-gateway /v1/embeddings 'data' must be a list; got "
            f"{type(data).__name__}"
        )
    parsed: list[list[float]] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict) or "embedding" not in item:
            raise ValueError(
                f"aigc-gateway /v1/embeddings data[{index}] missing "
                f"'embedding' key; got {item!r}"
            )
        vec = item["embedding"]
        if not isinstance(vec, list):
            raise ValueError(
                f"aigc-gateway /v1/embeddings data[{index}].embedding is "
                f"not a list; got {type(vec).__name__}"
            )
        parsed.append([float(value) for value in vec])
    return parsed
