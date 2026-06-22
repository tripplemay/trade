"""B073 F001 — LLM gateway VCR replay (offline, no key, no network).

Complements ``test_llm_gateway.py`` (in-process fake client). The gateway builds
its *real* ``httpx.Client``; pytest-recording replays a committed cassette so the
OpenAI-compatible ``/v1/chat/completions`` round-trip — task→model routing, POST
shape, ``choices[0].message.content`` parse, ``id`` → ``aigc_log_id`` mapping —
runs end to end without a live ``AIGC_GATEWAY_API_KEY``.
"""

from __future__ import annotations

import pytest

from workbench_api.llm.gateway import ChatRequest, ChatResult, LLMGateway


class _NoopGuard:
    """Cost guard that never raises or touches the DB (offline isolation)."""

    def check_and_increment(self, *, estimated_cost_usd: float) -> None:
        return None


@pytest.mark.vcr
def test_llm_gateway_advise_replays_offline() -> None:
    """Real httpx client + committed cassette → deterministic ChatResult."""

    gateway = LLMGateway(api_key="vcr-test-key", guard=_NoopGuard())

    result: ChatResult = gateway.advise(
        ChatRequest(
            task="daily_advisor",
            messages=[{"role": "user", "content": "Summarise today's drift."}],
            max_tokens=128,
            temperature=0.2,
        )
    )

    assert result.model_used == "claude-haiku-4.5"
    assert result.content.startswith("Today's portfolio drift is within tolerance")
    assert result.aigc_log_id == "chatcmpl-2026-05-27-daily-001"
    assert result.input_tokens == 84
    assert result.output_tokens == 31
