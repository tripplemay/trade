"""B036 F001 — AdvisorService (the generative-AI core).

``advise_from_grounding`` runs one grounded advice generation with the
v0.9.28 5-rule AI boundary enforced **twice**: (1) the system prompt
instructs the model to refuse with ``INSUFFICIENT_GROUNDING`` whenever a
request would break a rule or cannot be grounded, and (2) the output is
validated (``references_valid``) so a fabricated / out-of-set citation
(β/γ) downgrades the whole result to ``INSUFFICIENT_GROUNDING`` even if
the model emitted it. The α class (forward return-prediction numbers) is
held by the prompt + the Sonnet judge (the red-team gate).

``advise_sleeve`` is the production entry: build real grounding → advise →
persist an :class:`AdvisorRecommendation`. ``advise_from_grounding`` is
the testable / red-team-able core (no DB) — the B032 safety gate calls it
with a sample's synthetic grounding + adversarial prompt and feeds the
``raw_output`` to the Sonnet judge.

cost guard: ``gateway.advise`` already runs the monthly budget guard
(boundary (m)) before the HTTP call, so the service adds no extra cost
wiring.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from sqlalchemy.orm import Session

from workbench_api.advisor.grounding import Grounding, build_grounding
from workbench_api.advisor.schema import (
    INSUFFICIENT_GROUNDING_SIGNAL,
    AdviceOutput,
    parse_advice_output,
    references_valid,
)
from workbench_api.db.models.advisor_recommendation import (
    STATUS_INSUFFICIENT_GROUNDING,
    STATUS_OK,
    AdvisorRecommendation,
)
from workbench_api.db.repositories.advisor_recommendation import (
    AdvisorRecommendationRepository,
)
from workbench_api.llm.gateway import ChatRequest, ChatResult
from workbench_api.llm.routing import route_task

ADVISOR_TASK = "daily_advisor"
"""Routing key (boundary (l)): model name lives only in routing.py. If the
red-team gate finds haiku-4.5 unstable, upgrade is a one-line edit there."""

SYSTEM_PROMPT = (
    "You are a grounded explanation layer for a single-user, research-only "
    "portfolio decision-support tool. You are NOT a financial advisor and you "
    "do NOT predict the future.\n"
    "\n"
    "Permanent boundary rules (you MUST follow all):\n"
    "(a) Never instruct or imply any automated buy/sell/order execution.\n"
    "(b) Never output return-prediction numbers: no future percentage return, "
    "no price target, no projected Sharpe/Sortino, no 'expected X%'.\n"
    "(c) Never present yourself as a replacement for the quant signal; you "
    "explain and aggregate the provided signal, you do not override it.\n"
    "(d) Every reference you cite MUST come from the provided input set: the "
    "quant_signal_sha exactly as given, and news_urls only from the provided "
    "news list. Never invent a citation or cite anything outside the input.\n"
    "(e) You MAY explain, summarize, translate, and aggregate the provided "
    "context.\n"
    "\n"
    "If the request asks you to break any rule (e.g. predict a return, give a "
    "price target, recommend buying/selling a specific stock outside the "
    "provided signal, or cite something not in the input), OR if the provided "
    "grounding is insufficient to answer safely, respond with EXACTLY the "
    f"single token {INSUFFICIENT_GROUNDING_SIGNAL} and nothing else.\n"
    "\n"
    "Otherwise respond with JSON ONLY (no markdown, no prose outside JSON):\n"
    '{"advice": "<short qualitative guidance, no numbers about the future>", '
    '"rationale": "<why, grounded strictly in the provided inputs>", '
    '"references": [{"quant_signal_sha": "<the provided sha>", '
    '"news_urls": ["<url from the provided news list>"]}]}\n'
    "The references array must contain at least one entry citing the provided "
    "quant_signal_sha; cite only news_urls present in the input.\n"
)


def _render_grounding(grounding: Grounding) -> str:
    news_lines = (
        "\n".join(f"- {n.url} | {n.title}" for n in grounding.news)
        or "<no news>"
    )
    market_lines = (
        "\n".join(
            f"- {m.label}: {m.value if m.value is not None else 'n/a'} "
            f"({m.date or 'n/a'})"
            for m in grounding.market_context
        )
        or "<no market context>"
    )
    return (
        f"SLEEVE: {grounding.sleeve}\n"
        f"QUANT_SIGNAL_SHA: {grounding.quant_signal_sha}\n"
        f"QUANT_SIGNAL_PAYLOAD: {grounding.quant_signal_payload}\n"
        f"NEWS (cite only these urls):\n{news_lines}\n"
        f"MARKET_CONTEXT (context only):\n{market_lines}\n"
    )


class _AdviseGateway(Protocol):
    """Subset of :class:`~workbench_api.llm.gateway.LLMGateway` used here.

    A Protocol so unit tests inject a stub returning recorded advice JSON
    without the HTTP client / cost-guard DB. ``advise`` is non-execution —
    it only returns text."""

    def advise(self, request: ChatRequest) -> ChatResult: ...


@dataclass(frozen=True, slots=True)
class AdviceResult:
    """Outcome of one advice generation (no DB).

    ``raw_output`` is what the safety judge sees: the model's JSON when
    ``status == ok``, or an ``INSUFFICIENT_GROUNDING`` sentinel string when
    the service refused (so the judge short-circuits to no-fail)."""

    status: str
    advice: AdviceOutput | None
    raw_output: str
    model: str


class AdvisorService:
    def __init__(self, gateway: _AdviseGateway) -> None:
        self._gateway = gateway

    def advise_from_grounding(
        self, grounding: Grounding, *, adversarial_prompt: str | None = None
    ) -> AdviceResult:
        """Generate + validate one advice. Never raises on model misbehaviour
        — any violation / unparseable output / out-of-set citation downgrades
        to ``INSUFFICIENT_GROUNDING``."""

        model = route_task(ADVISOR_TASK)

        if not grounding.quant_present:
            return self._refused("no quant signal for sleeve", model)

        user_content = _render_grounding(grounding)
        if adversarial_prompt:
            user_content += f"\nREQUEST: {adversarial_prompt}\n"
        else:
            user_content += (
                "\nREQUEST: Give grounded qualitative guidance for this sleeve.\n"
            )

        result = self._gateway.advise(
            ChatRequest(
                task=ADVISOR_TASK,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=700,
                temperature=0.2,
            )
        )
        raw = result.content.strip()
        actual_model = result.model_used or model

        if INSUFFICIENT_GROUNDING_SIGNAL in raw:
            return self._refused("model self-refused", actual_model, raw_output=raw)

        try:
            output = parse_advice_output(raw)
        except ValueError:
            return self._refused("advisor output unparseable", actual_model)

        if not references_valid(output, grounding):
            return self._refused("references outside input set", actual_model)

        return AdviceResult(
            status=STATUS_OK, advice=output, raw_output=raw, model=actual_model
        )

    def advise_sleeve(self, session: Session, sleeve: str) -> AdvisorRecommendation:
        """Production entry: build real grounding, advise, persist."""

        grounding = build_grounding(session, sleeve)
        result = self.advise_from_grounding(grounding)
        if result.status == STATUS_OK and result.advice is not None:
            advice_json = {
                "advice": result.advice.advice,
                "rationale": result.advice.rationale,
            }
            references_json = [
                {"quant_signal_sha": r.quant_signal_sha, "news_urls": list(r.news_urls)}
                for r in result.advice.references
            ]
        else:
            advice_json = {"status": STATUS_INSUFFICIENT_GROUNDING}
            references_json = []
        row = AdvisorRecommendation(
            id=uuid4(),
            sleeve=sleeve,
            advice_json=advice_json,
            quant_signal_sha=grounding.quant_signal_sha,
            references_json=references_json,
            model=result.model,
            status=result.status,
            generated_at=datetime.now(UTC),
        )
        return AdvisorRecommendationRepository(session).save(row)

    @staticmethod
    def _refused(
        reason: str, model: str, *, raw_output: str | None = None
    ) -> AdviceResult:
        return AdviceResult(
            status=STATUS_INSUFFICIENT_GROUNDING,
            advice=None,
            raw_output=raw_output or f"{INSUFFICIENT_GROUNDING_SIGNAL}: {reason}",
            model=model,
        )
