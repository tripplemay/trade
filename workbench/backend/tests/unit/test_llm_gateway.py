"""B031 F001 — LLMGateway behaviour.

The tests inject a fake HTTP client so the entire suite stays offline
(CI requirement) and so each adversarial scenario — auth failure, 5xx
storm, rate-limit reply, malformed payload — can be asserted
deterministically. Real aigc-gateway HTTP traffic is verified once at
L2 by the evaluator (B031 F003 spec acceptance §7).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from workbench_api.llm.gateway import (
    AIGC_GATEWAY_BASE_URL,
    ChatRequest,
    ChatResult,
    LLMGateway,
)

FIXTURES_DIR = (
    Path(__file__).resolve().parents[2]
    / "workbench_api"
    / "llm"
    / "fixtures"
)


def _load_fixture(name: str) -> dict[str, Any]:
    """Read a JSON fixture from the LLM module's fixtures directory."""

    path = FIXTURES_DIR / name
    payload: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return payload


class _StubGuard:
    """No-op guard that records the estimated cost of each call.

    Lets tests assert the gateway invoked the guard with the right
    cost shape without standing up the F002 ``MonthlyBudgetGuard`` DB.
    """

    def __init__(self) -> None:
        self.estimates: list[float] = []

    def check_and_increment(self, *, estimated_cost_usd: float) -> None:
        self.estimates.append(estimated_cost_usd)


class _ExceededGuard:
    """Stand-in for a cost guard whose monthly cap is already hit."""

    def check_and_increment(self, *, estimated_cost_usd: float) -> None:
        raise RuntimeError("budget exceeded in test")


class _StubResponse:
    """Minimal stand-in for ``httpx.Response`` the gateway touches."""

    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload
        self.request = httpx.Request("POST", "https://aigc-gateway.example.com/fake")

    def json(self) -> Any:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"stub {self.status_code}",
                request=self.request,
                response=self,  # type: ignore[arg-type]
            )


class _StubClient:
    """Stand-in for ``httpx.Client`` driving the gateway through a
    scripted sequence of responses or raised network errors."""

    def __init__(
        self,
        responses: list[_StubResponse | Exception] | None = None,
    ) -> None:
        self._responses: list[_StubResponse | Exception] = list(responses or [])
        self.posts: list[tuple[str, dict[str, Any]]] = []
        self.gets: list[str] = []

    def post(self, url: str, json: dict[str, Any]) -> _StubResponse:  # noqa: A002
        self.posts.append((url, dict(json)))
        return self._next(url)

    def get(self, url: str) -> _StubResponse:
        self.gets.append(url)
        return self._next(url)

    def _next(self, url: str) -> _StubResponse:
        if not self._responses:
            raise AssertionError(f"StubClient ran out of scripted responses for {url}")
        nxt = self._responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt


def _make_gateway(
    *,
    client: _StubClient,
    guard: _StubGuard | _ExceededGuard | None = None,
) -> LLMGateway:
    """Build an LLMGateway wired against the stub HTTP client."""

    return LLMGateway(
        api_key="k-test",
        client=client,
        sleep=lambda _s: None,
        guard=guard or _StubGuard(),
    )


# --- Dataclass shape -----------------------------------------------------


def test_chat_request_is_frozen_with_slots() -> None:
    """Immutability + slots keep the request hashable and prevent
    accidental mutation across a retry loop."""

    request = ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "hi"}])
    with pytest.raises((AttributeError, TypeError)):
        request.task = "news_summarize"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        request.note = "should not stick"  # type: ignore[attr-defined]


def test_chat_result_is_frozen_with_slots() -> None:
    """Same invariant for results so a caller cannot mutate a returned
    record before persisting it to a log."""

    result = ChatResult(
        content="hello",
        model_used="claude-haiku-4-5",
        input_tokens=1,
        output_tokens=2,
        cost_usd_est=0.0001,
        aigc_log_id="x",
    )
    with pytest.raises((AttributeError, TypeError)):
        result.content = "tampered"  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        result.extra = "no"  # type: ignore[attr-defined]


# --- Constructor + API key resolution -----------------------------------


def test_missing_api_key_raises_with_setup_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constructor must fail loudly with a fix pointer when the
    env var is missing — production callers cannot silently fall back."""

    monkeypatch.delenv("AIGC_GATEWAY_API_KEY", raising=False)
    with pytest.raises(RuntimeError) as exc_info:
        LLMGateway()
    message = str(exc_info.value)
    assert "AIGC_GATEWAY_API_KEY" in message
    assert "mcp__aigc-gateway__create_api_key" in message
    assert "GitHub repo" in message


def test_api_key_resolves_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the explicit kwarg is omitted, the env var feeds the key."""

    monkeypatch.setenv("AIGC_GATEWAY_API_KEY", "env-key-xyz")
    gateway = LLMGateway(client=_StubClient(), sleep=lambda _s: None, guard=_StubGuard())
    assert gateway.api_key == "env-key-xyz"


def test_base_url_strips_trailing_slash() -> None:
    """Caller may pass a trailing slash; the gateway must normalise
    so URL concatenation stays consistent."""

    gateway = LLMGateway(
        api_key="k",
        base_url="https://example.com/api/",
        client=_StubClient(),
        sleep=lambda _s: None,
        guard=_StubGuard(),
    )
    assert gateway.base_url == "https://example.com/api"


def test_default_base_url_matches_module_constant() -> None:
    """The default base URL must match the module-level constant so a
    config drift here is caught by the unit test, not by a production
    misroute."""

    gateway = LLMGateway(
        api_key="k", client=_StubClient(), sleep=lambda _s: None, guard=_StubGuard()
    )
    assert gateway.base_url == AIGC_GATEWAY_BASE_URL.rstrip("/")


# --- advise() happy + adversarial paths --------------------------------


def test_advise_parses_chat_payload_into_chat_result() -> None:
    """Happy-path parse mirrors aigc-gateway's documented /chat schema."""

    payload = _load_fixture("aigc_gateway_chat_responses/sample_daily_advisor.json")
    client = _StubClient([_StubResponse(200, payload)])
    gateway = _make_gateway(client=client)
    result = gateway.advise(
        ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "Hi"}])
    )
    assert isinstance(result, ChatResult)
    assert result.model_used == "claude-haiku-4-5"
    assert result.input_tokens == 84
    assert result.output_tokens == 31
    assert result.aigc_log_id == "aigc-log-2026-05-27-daily-001"


def test_advise_routes_task_through_routing_table() -> None:
    """advise() must place the routed model into the POST body — the
    permanent boundary (l) is enforced by always using the routing
    table even on the wire."""

    payload = _load_fixture("aigc_gateway_chat_responses/sample_news_summarize.json")
    client = _StubClient([_StubResponse(200, payload)])
    gateway = _make_gateway(client=client)
    gateway.advise(
        ChatRequest(
            task="news_summarize",
            messages=[{"role": "user", "content": "Latest headlines"}],
        )
    )
    assert len(client.posts) == 1
    _url, body = client.posts[0]
    assert body["model"] == "gemini-2.0-flash"


def test_advise_unknown_task_raises_before_network_call() -> None:
    """Permanent boundary (l): an unknown task must raise before any
    HTTP call, so a typo never lands a request with a bogus model."""

    client = _StubClient([_StubResponse(200, {})])  # Should never be consumed.
    gateway = _make_gateway(client=client)
    with pytest.raises(RuntimeError):
        gateway.advise(
            ChatRequest(task="not_a_real_task", messages=[{"role": "user", "content": "x"}])
        )
    assert client.posts == []


def test_advise_retries_on_5xx_then_succeeds() -> None:
    """3-attempt retry policy: two 503s then a 200 → caller sees success."""

    payload = _load_fixture("aigc_gateway_chat_responses/sample_daily_advisor.json")
    client = _StubClient(
        [
            _StubResponse(503, {"detail": "transient"}),
            _StubResponse(502, {"detail": "transient"}),
            _StubResponse(200, payload),
        ]
    )
    sleeps: list[float] = []
    gateway = LLMGateway(
        api_key="k", client=client, sleep=lambda s: sleeps.append(s), guard=_StubGuard()
    )
    result = gateway.advise(
        ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "Hi"}])
    )
    assert result.content.startswith("Today's portfolio")
    assert sleeps == [0.5, 1.0]


def test_advise_retries_on_429_rate_limit() -> None:
    """429 must trigger the same backoff path as 5xx — gateway-side
    rate limiting (e.g. provider quota exhausted) is a transient
    condition."""

    payload = _load_fixture("aigc_gateway_chat_responses/sample_daily_advisor.json")
    client = _StubClient(
        [
            _StubResponse(429, {"detail": "rate limit"}),
            _StubResponse(200, payload),
        ]
    )
    sleeps: list[float] = []
    gateway = LLMGateway(
        api_key="k", client=client, sleep=lambda s: sleeps.append(s), guard=_StubGuard()
    )
    result = gateway.advise(
        ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "Hi"}])
    )
    assert result.input_tokens == 84
    assert sleeps == [0.5]


def test_advise_exhausts_retries_and_raises() -> None:
    """After MAX_RETRIES sustained 5xx, the last error propagates so
    the caller can decide whether to alert + skip the request."""

    client = _StubClient(
        [
            _StubResponse(500, {"detail": "boom"}),
            _StubResponse(500, {"detail": "boom"}),
            _StubResponse(500, {"detail": "boom"}),
        ]
    )
    gateway = _make_gateway(client=client)
    with pytest.raises(httpx.HTTPStatusError):
        gateway.advise(
            ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "x"}])
        )


def test_advise_invokes_guard_before_http_with_estimated_cost() -> None:
    """The guard must be invoked exactly once per advise call, with
    the estimated cost, BEFORE the HTTP layer sees anything. Order
    matters so a tripped cap halts the call before paying network
    time."""

    payload = _load_fixture("aigc_gateway_chat_responses/sample_daily_advisor.json")
    client = _StubClient([_StubResponse(200, payload)])
    guard = _StubGuard()
    gateway = _make_gateway(client=client, guard=guard)
    gateway.advise(
        ChatRequest(
            task="daily_advisor",
            messages=[{"role": "user", "content": "Should I rebalance today?"}],
        )
    )
    assert len(guard.estimates) == 1
    # Estimated cost must be > 0 (Haiku has nonzero input/output prices).
    assert guard.estimates[0] > 0


def test_advise_skips_http_when_guard_raises() -> None:
    """A guard raise (budget exceeded, etc.) must propagate out of
    advise() and the HTTP client must remain untouched — the whole
    point of the cap is to stop the network call BEFORE it happens."""

    client = _StubClient([_StubResponse(200, {"content": "x"})])
    gateway = _make_gateway(client=client, guard=_ExceededGuard())
    with pytest.raises(RuntimeError):
        gateway.advise(
            ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "x"}])
        )
    assert client.posts == []


def test_advise_raises_on_missing_content_field() -> None:
    """aigc-gateway schema drift surfaces as a ValueError so a vendor
    change cannot silently produce a ChatResult with empty content."""

    client = _StubClient([_StubResponse(200, {"model": "claude-haiku-4-5"})])  # no content
    gateway = _make_gateway(client=client)
    with pytest.raises(ValueError) as exc_info:
        gateway.advise(
            ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "x"}])
        )
    assert "content" in str(exc_info.value)


def test_advise_raises_on_non_dict_payload() -> None:
    """A non-dict top-level payload (HTML error page, plain string) is
    a schema violation and must not be parsed into a ChatResult."""

    client = _StubClient([_StubResponse(200, ["unexpected", "list"])])
    gateway = _make_gateway(client=client)
    with pytest.raises(ValueError) as exc_info:
        gateway.advise(
            ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "x"}])
        )
    assert "non-dict" in str(exc_info.value)


def test_advise_retries_on_network_error() -> None:
    """A connection-layer error (DNS, TLS, socket) is treated like a
    5xx — the backoff loop gets a chance before the run is given up."""

    payload = _load_fixture("aigc_gateway_chat_responses/sample_daily_advisor.json")
    client = _StubClient(
        [
            httpx.ConnectError("temporary dns failure"),
            _StubResponse(200, payload),
        ]
    )
    gateway = _make_gateway(client=client)
    result = gateway.advise(
        ChatRequest(task="daily_advisor", messages=[{"role": "user", "content": "x"}])
    )
    assert result.model_used == "claude-haiku-4-5"


# --- embed() ----------------------------------------------------------


def test_embed_returns_parsed_vectors() -> None:
    """Embedding endpoint returns one vector per input text."""

    client = _StubClient(
        [_StubResponse(200, {"vectors": [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]})]
    )
    gateway = _make_gateway(client=client)
    vectors = gateway.embed(["alpha", "beta", "gamma"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]]


def test_embed_routes_to_cohere_multilingual_by_default() -> None:
    """Default routing for ``task='embedding'`` is the Cohere
    multilingual v3 model per llm-provider-evaluation §5.2."""

    client = _StubClient([_StubResponse(200, {"vectors": [[0.0]]})])
    gateway = _make_gateway(client=client)
    gateway.embed(["one"])
    _url, body = client.posts[0]
    assert body["model"] == "cohere-embed-multilingual-v3"


def test_embed_raises_on_missing_vectors_field() -> None:
    """A payload without ``vectors`` is a schema violation."""

    client = _StubClient([_StubResponse(200, {"unexpected": "shape"})])
    gateway = _make_gateway(client=client)
    with pytest.raises(ValueError):
        gateway.embed(["x"])


# --- health_check() ---------------------------------------------------


def test_health_check_returns_true_on_balance_200() -> None:
    """A 200 from /balance signals the gateway is reachable + key valid."""

    payload = _load_fixture("aigc_gateway_balance_response.json")
    client = _StubClient([_StubResponse(200, payload)])
    gateway = _make_gateway(client=client)
    assert gateway.health_check() is True
    assert client.gets == [f"{gateway.base_url}/balance"]


def test_health_check_returns_false_on_auth_failure() -> None:
    """A 401 must surface as ``health_check() -> False`` so the
    caller can distinguish key-invalid from gateway-down."""

    client = _StubClient([_StubResponse(401, {"detail": "Not authorized"})])
    gateway = _make_gateway(client=client)
    assert gateway.health_check() is False


def test_health_check_does_not_invoke_guard() -> None:
    """The probe is metadata-only; it must not count against the
    monthly cap. Spec §F003 L2 §7 verifies smoke health_check does
    not increment llm_budget_log."""

    payload = _load_fixture("aigc_gateway_balance_response.json")
    client = _StubClient([_StubResponse(200, payload)])
    guard = _StubGuard()
    gateway = _make_gateway(client=client, guard=guard)
    gateway.health_check()
    assert guard.estimates == []
