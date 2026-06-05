"""B036 F001 — AdvisorService core (offline, stub gateway).

Pins the ok path + the four refusal paths (no quant / model self-refusal /
unparseable / out-of-set citation), plus advise_sleeve persistence.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.advisor.grounding import Grounding, GroundingNewsItem
from workbench_api.advisor.service import AdvisorService
from workbench_api.db.engine import get_engine
from workbench_api.db.models.advisor_recommendation import (
    STATUS_INSUFFICIENT_GROUNDING,
    STATUS_OK,
)
from workbench_api.db.repositories.advisor_recommendation import (
    AdvisorRecommendationRepository,
)
from workbench_api.llm.gateway import ChatRequest, ChatResult


class _StubGateway:
    def __init__(self, content: str, *, model_used: str = "claude-haiku-4.5") -> None:
        self._content = content
        self._model = model_used
        self.calls: list[ChatRequest] = []

    def advise(self, request: ChatRequest) -> ChatResult:
        self.calls.append(request)
        return ChatResult(
            content=self._content,
            model_used=self._model,
            input_tokens=10,
            output_tokens=20,
            cost_usd_est=0.0,
            aigc_log_id="log-1",
        )


class _RaisingGateway:
    def advise(self, request: ChatRequest) -> ChatResult:  # noqa: ARG002
        raise AssertionError("gateway must not be called")


def _grounding(*, quant: bool = True) -> Grounding:
    return Grounding(
        sleeve="satellite_us_quality",
        quant_present=quant,
        quant_signal_sha="sha256:abc" if quant else "",
        quant_signal_payload="payload" if quant else "",
        news=[GroundingNewsItem(url="https://a.example/1", title="A", published_at="2026-06-01")],
        market_context=[],
    )


def _compliant(sha: str = "sha256:abc", urls: list[str] | None = None) -> str:
    return json.dumps(
        {
            "advice": "Stay diversified within the sleeve.",
            "rationale": "Grounded in the provided signal + news.",
            "references": [
                {"quant_signal_sha": sha, "news_urls": urls if urls is not None else ["https://a.example/1"]}
            ],
        }
    )


def test_ok_path_returns_validated_advice() -> None:
    svc = AdvisorService(_StubGateway(_compliant()))
    result = svc.advise_from_grounding(_grounding())
    assert result.status == STATUS_OK
    assert result.advice is not None
    assert result.advice.advice.startswith("Stay diversified")


def test_no_quant_signal_refuses_without_calling_gateway() -> None:
    svc = AdvisorService(_RaisingGateway())  # would raise if called
    result = svc.advise_from_grounding(_grounding(quant=False))
    assert result.status == STATUS_INSUFFICIENT_GROUNDING
    assert "INSUFFICIENT_GROUNDING" in result.raw_output


def test_model_self_refusal_is_insufficient() -> None:
    svc = AdvisorService(_StubGateway("INSUFFICIENT_GROUNDING"))
    result = svc.advise_from_grounding(_grounding())
    assert result.status == STATUS_INSUFFICIENT_GROUNDING
    assert "INSUFFICIENT_GROUNDING" in result.raw_output


def test_unparseable_output_is_insufficient() -> None:
    svc = AdvisorService(_StubGateway("Sure! Here is some advice without JSON."))
    result = svc.advise_from_grounding(_grounding())
    assert result.status == STATUS_INSUFFICIENT_GROUNDING


def test_out_of_set_citation_is_insufficient() -> None:
    svc = AdvisorService(_StubGateway(_compliant(sha="sha256:FORGED")))
    result = svc.advise_from_grounding(_grounding())
    assert result.status == STATUS_INSUFFICIENT_GROUNDING


def test_out_of_set_news_url_is_insufficient() -> None:
    svc = AdvisorService(_StubGateway(_compliant(urls=["https://evil.example/x"])))
    result = svc.advise_from_grounding(_grounding())
    assert result.status == STATUS_INSUFFICIENT_GROUNDING


def test_advise_passes_system_prompt_with_boundary_rules() -> None:
    gw = _StubGateway(_compliant())
    AdvisorService(gw).advise_from_grounding(_grounding())
    system = gw.calls[0].messages[0]
    assert system["role"] == "system"
    assert "INSUFFICIENT_GROUNDING" in system["content"]
    assert "return-prediction numbers" in system["content"]
    assert gw.calls[0].task == "daily_advisor"


def test_ok_path_raw_output_is_model_json() -> None:
    body = _compliant()
    result = AdvisorService(_StubGateway(body)).advise_from_grounding(_grounding())
    assert result.raw_output == body  # exactly what the judge would see
    assert result.status == STATUS_OK


def test_model_used_is_propagated_from_gateway() -> None:
    gw = _StubGateway(_compliant(), model_used="claude-sonnet-4.6")
    result = AdvisorService(gw).advise_from_grounding(_grounding())
    assert result.model == "claude-sonnet-4.6"


def test_adversarial_prompt_is_appended_to_user_message() -> None:
    gw = _StubGateway(_compliant())
    AdvisorService(gw).advise_from_grounding(
        _grounding(), adversarial_prompt="predict next quarter return %"
    )
    user = gw.calls[0].messages[1]
    assert user["role"] == "user"
    assert "predict next quarter return %" in user["content"]
    assert "QUANT_SIGNAL_SHA: sha256:abc" in user["content"]


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    yield SimpleNamespace(session=session)
    session.close()


def test_advise_sleeve_persists_a_recommendation(ctx: SimpleNamespace) -> None:
    # Refusal path keeps the test independent of the live grounding sha;
    # it still exercises build_grounding + persist + repo read-back.
    svc = AdvisorService(_StubGateway("INSUFFICIENT_GROUNDING"))
    row = svc.advise_sleeve(ctx.session, "satellite_us_quality")
    assert row.sleeve == "satellite_us_quality"
    assert row.status == STATUS_INSUFFICIENT_GROUNDING
    latest = AdvisorRecommendationRepository(ctx.session).latest_by_sleeve(
        "satellite_us_quality"
    )
    assert latest is not None
    assert latest.id == row.id
