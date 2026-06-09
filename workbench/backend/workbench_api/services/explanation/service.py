"""B043 — ExplanationService: the grounded-explanation core.

Generic over the three injection points (recommendation rationale / backtest /
risk). Each caller passes a routing ``task``, a rendered ``grounding`` block
(the real already-computed values), the set of ``citable`` tokens, and a
``request_line``; the service runs one guarded generation and returns the short
explanation — or a refusal that callers degrade to a deterministic placeholder.

Reuses the advisor guardrail chain shape (B036): the system prompt enforces the
no-AI 5 rules + a refusal sentinel, and the output is validated
(``references_grounded``) so a fabricated / out-of-set citation downgrades the
whole result. ``gateway.advise`` already runs the monthly cost guard (boundary
(m)) before the HTTP call, so this adds no extra cost wiring. Never raises on
model misbehaviour — any violation / unparseable output / out-of-set citation
becomes INSUFFICIENT_GROUNDING.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from workbench_api.llm.gateway import ChatRequest, ChatResult
from workbench_api.llm.routing import route_task
from workbench_api.services.explanation.schema import (
    INSUFFICIENT_GROUNDING_SIGNAL,
    parse_explanation_output,
    references_grounded,
)

STATUS_OK = "ok"
STATUS_INSUFFICIENT_GROUNDING = "insufficient_grounding"

SYSTEM_PROMPT = (
    "You are a grounded explanation layer for a single-user, research-only "
    "portfolio decision-support tool. You explain real, ALREADY-COMPUTED values. "
    "You are NOT a financial advisor and you do NOT predict the future.\n"
    "\n"
    "Permanent boundary rules (you MUST follow all):\n"
    "(a) Never instruct or imply any automated buy/sell/order execution.\n"
    "(b) Never output return-prediction numbers: no future percentage return, no "
    "price target, no projected or 'expected' Sharpe/return. You MAY restate the "
    "real, already-computed numbers given in the input.\n"
    "(c) Never present yourself as a replacement for the quant signal; you explain "
    "the provided values, you do not override them.\n"
    "(d) Every value, date, or token you reference MUST come from the provided "
    "input. Never invent a number, weight, date, or citation.\n"
    "(e) You MAY explain, summarize, translate, and aggregate the provided context.\n"
    "\n"
    "If the request would break a rule, or the provided grounding is insufficient "
    f"to answer safely, respond with EXACTLY the single token "
    f"{INSUFFICIENT_GROUNDING_SIGNAL} and nothing else.\n"
    "\n"
    "Otherwise respond with JSON ONLY (no markdown, no prose outside JSON):\n"
    '{"explanation": "<1-2 sentence plain-language why, grounded strictly in the '
    'inputs>", "references": ["<input token you used>", ...]}\n'
    "references must list at least one token copied verbatim from the input "
    "(e.g. a SLEEVE name, a SIGNAL_DATE, a DATA_SOURCE, or a metric label); cite "
    "only tokens present in the input.\n"
)


class _AdviseGateway(Protocol):
    """Subset of :class:`~workbench_api.llm.gateway.LLMGateway` used here — a
    Protocol so tests inject a stub returning recorded JSON without the HTTP
    client / cost-guard DB. ``advise`` is non-execution; it only returns text."""

    def advise(self, request: ChatRequest) -> ChatResult: ...


@dataclass(frozen=True, slots=True)
class ExplanationResult:
    """Outcome of one explanation generation (no DB).

    ``raw_output`` is what a safety judge sees: the model's JSON when
    ``status == ok``, or a sentinel string when the service refused."""

    status: str
    explanation: str | None
    raw_output: str
    model: str


class ExplanationService:
    def __init__(self, gateway: _AdviseGateway) -> None:
        self._gateway = gateway

    def explain(
        self,
        *,
        task: str,
        grounding_text: str,
        citable: Iterable[str],
        request_line: str,
        max_tokens: int = 320,
    ) -> ExplanationResult:
        """Generate + validate one grounded explanation. Never raises on model
        misbehaviour — any violation / unparseable output / out-of-set citation
        downgrades to INSUFFICIENT_GROUNDING (callers degrade to a placeholder).
        A cost-guard trip / HTTP error DOES propagate so the caller's degrade
        path records it."""

        model = route_task(task)
        result = self._gateway.advise(
            ChatRequest(
                task=task,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"{grounding_text}\nREQUEST: {request_line}\n"},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
        )
        raw = result.content.strip()
        actual_model = result.model_used or model

        if INSUFFICIENT_GROUNDING_SIGNAL in raw:
            return self._refused("model self-refused", actual_model, raw_output=raw)
        try:
            output = parse_explanation_output(raw)
        except ValueError:
            return self._refused("explanation output unparseable", actual_model)
        if not references_grounded(output, citable):
            return self._refused("references outside input set", actual_model)
        if not output.explanation:
            return self._refused("empty explanation", actual_model)

        return ExplanationResult(
            status=STATUS_OK,
            explanation=output.explanation,
            raw_output=raw,
            model=actual_model,
        )

    @staticmethod
    def _refused(
        reason: str, model: str, *, raw_output: str | None = None
    ) -> ExplanationResult:
        return ExplanationResult(
            status=STATUS_INSUFFICIENT_GROUNDING,
            explanation=None,
            raw_output=raw_output or f"{INSUFFICIENT_GROUNDING_SIGNAL}: {reason}",
            model=model,
        )
