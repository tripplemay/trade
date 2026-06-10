"""B043 F001 — shared explanation layer + Recommendations rationale.

Covers the grounded-explanation core (guardrail chain reuse), its citation
contract, the recommendation rationale builder (degrade-to-placeholder), the
precompute injection + idempotent reuse, and the routing-task registration.
All offline — the gateway is a stub; no network, no key.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.recommendation_snapshot import DATA_SOURCE_REAL
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.llm.gateway import ChatRequest, ChatResult
from workbench_api.llm.judge import INSUFFICIENT_GROUNDING_SIGNAL
from workbench_api.llm.routing import estimate_cost_usd, route_task
from workbench_api.recommendations.precompute import MasterTargetResult, run_precompute
from workbench_api.recommendations.rationale import (
    deterministic_rationale,
    generate_rationale,
)
from workbench_api.services.explanation import (
    STATUS_OK,
    ExplanationResult,
    ExplanationService,
    parse_explanation_output,
    references_grounded,
)


class _StubGateway:
    """Records the request + returns a scripted ChatResult (no network)."""

    def __init__(self, content: str) -> None:
        self._content = content
        self.calls: list[ChatRequest] = []

    def advise(self, request: ChatRequest) -> ChatResult:
        self.calls.append(request)
        return ChatResult(
            content=self._content,
            model_used="claude-haiku-4.5",
            input_tokens=1,
            output_tokens=1,
            cost_usd_est=0.0,
            aigc_log_id="stub",
        )


_OK_JSON = (
    '{"explanation": "AAPL sits in the satellite_us_quality sleeve, weighted by '
    'its quarter-end signal on 2026-03-31.", "references": '
    '["satellite_us_quality", "2026-03-31"]}'
)
_GROUNDING = (
    "SYMBOL: AAPL\nSLEEVE: satellite_us_quality\nTARGET_WEIGHT: 0.0123\n"
    "SLEEVE_STATUS: scored\nDATA_SOURCE: real\nSIGNAL_DATE: 2026-03-31\n"
)


# --- routing -------------------------------------------------------------------


@pytest.mark.parametrize(
    "task", ["recommendation_rationale", "backtest_explanation", "risk_explanation"]
)
def test_explanation_tasks_route_to_haiku(task: str) -> None:
    model = route_task(task)
    assert model == "claude-haiku-4.5"
    # PRICE_TABLE covers it (no zero-cost silent bypass).
    assert estimate_cost_usd(model, 100, 100) > 0


# --- schema --------------------------------------------------------------------


def test_parse_explanation_tolerates_code_fence() -> None:
    out = parse_explanation_output(f"```json\n{_OK_JSON}\n```")
    assert "satellite_us_quality" in out.explanation
    assert out.references == ["satellite_us_quality", "2026-03-31"]


def test_references_grounded_accepts_substrings_rejects_fabricated_and_empty() -> None:
    # Real models cite grounding tokens in varied forms (bare value or labelled
    # line) — both are substrings of the grounding we provided.
    out = parse_explanation_output(_OK_JSON)
    assert references_grounded(out, _GROUNDING) is True
    labelled = parse_explanation_output(
        '{"explanation": "x", "references": ["SIGNAL_DATE: 2026-03-31", "SLEEVE_STATUS: scored"]}'
    )
    assert references_grounded(labelled, _GROUNDING) is True  # labelled lines OK
    fabricated = parse_explanation_output(
        '{"explanation": "x", "references": ["expected 18% return next year"]}'
    )
    assert references_grounded(fabricated, _GROUNDING) is False  # not in grounding
    empty = parse_explanation_output('{"explanation": "x", "references": []}')
    assert references_grounded(empty, _GROUNDING) is False  # no citation


# --- ExplanationService --------------------------------------------------------


def _explain(content: str) -> ExplanationResult:
    service = ExplanationService(_StubGateway(content))
    return service.explain(
        task="recommendation_rationale",
        grounding_text=_GROUNDING,
        request_line="why",
    )


def test_explain_ok_returns_grounded_explanation() -> None:
    result = _explain(_OK_JSON)
    assert result.status == STATUS_OK
    assert result.explanation is not None and "satellite_us_quality" in result.explanation


def test_explain_self_refusal_downgrades() -> None:
    assert _explain(INSUFFICIENT_GROUNDING_SIGNAL).status != STATUS_OK


def test_explain_unparseable_downgrades() -> None:
    assert _explain("not json at all").status != STATUS_OK


def test_explain_out_of_set_citation_downgrades() -> None:
    out_of_set = '{"explanation": "x", "references": ["FABRICATED_TICKER"]}'
    assert _explain(out_of_set).status != STATUS_OK


def test_explain_empty_explanation_downgrades() -> None:
    assert _explain('{"explanation": "", "references": ["AAPL"]}').status != STATUS_OK


# --- recommendation rationale (degrade) ----------------------------------------


class _StubExplainer:
    """Counts calls + returns a scripted ExplanationResult (or raises)."""

    def __init__(self, result: ExplanationResult | None = None, *, boom: bool = False) -> None:
        self._result = result
        self._boom = boom
        self.calls = 0

    def explain(self, **_kwargs: object) -> ExplanationResult:
        self.calls += 1
        if self._boom:
            raise RuntimeError("monthly budget cap reached")
        assert self._result is not None
        return self._result


def _ok_result() -> ExplanationResult:
    return ExplanationResult(
        status=STATUS_OK, explanation="grounded why", raw_output="{}", model="m"
    )


def _kwargs() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "sleeve": "satellite_us_quality",
        "target_weight": 0.012,
        "planning_weight": 0.2,
        "sleeve_status": "scored",
        "data_source": DATA_SOURCE_REAL,
        "signal_date": "2026-03-31",
    }


def test_generate_rationale_uses_llm_when_ok() -> None:
    explainer = _StubExplainer(_ok_result())
    assert generate_rationale(explainer, **_kwargs()) == "grounded why"  # type: ignore[arg-type]


def test_generate_rationale_degrades_to_placeholder_when_no_explainer() -> None:
    out = generate_rationale(None, **_kwargs())  # type: ignore[arg-type]
    assert out == deterministic_rationale("satellite_us_quality", DATA_SOURCE_REAL)


def test_generate_rationale_degrades_on_exception() -> None:
    explainer = _StubExplainer(boom=True)
    out = generate_rationale(explainer, **_kwargs())  # type: ignore[arg-type]
    assert out == deterministic_rationale("satellite_us_quality", DATA_SOURCE_REAL)
    assert explainer.calls == 1


def test_generate_rationale_degrades_on_refusal() -> None:
    refused = ExplanationResult(
        status="insufficient_grounding", explanation=None, raw_output="x", model="m"
    )
    out = generate_rationale(_StubExplainer(refused), **_kwargs())  # type: ignore[arg-type]
    assert out == deterministic_rationale("satellite_us_quality", DATA_SOURCE_REAL)


# --- precompute injection + idempotency ----------------------------------------


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _fake_result() -> MasterTargetResult:
    return MasterTargetResult(
        as_of_date=date(2026, 3, 31),
        target_weights={"AAPL": 0.2, "SGOV": 0.8},
        symbol_sleeve={"AAPL": "satellite_us_quality", "SGOV": "risk_parity"},
        master_meta={
            "data_source": DATA_SOURCE_REAL,
            "planning_weights": {"satellite_us_quality": 0.2, "risk_parity": 0.3},
            "sleeve_status": {"satellite_us_quality": "scored", "risk_parity": "scored"},
            "signal_date": "2026-03-31",
        },
    )


def test_run_precompute_injects_llm_rationale_then_reuses_idempotently(
    session: Session,
) -> None:
    explainer = _StubExplainer(_ok_result())
    # First run: LLM generates a rationale per symbol.
    s1 = run_precompute(session, score_fn=_fake_result, explainer=explainer)  # type: ignore[arg-type]
    assert s1.saved == 2
    assert explainer.calls == 2
    rows = RecommendationSnapshotRepository(session).latest_snapshot()
    assert {r.rationale for r in rows} == {"grounded why"}

    # Second run, same as_of_date: rationales reused, LLM NOT re-called (cost).
    s2 = run_precompute(session, score_fn=_fake_result, explainer=explainer)  # type: ignore[arg-type]
    assert s2.saved == 2
    assert explainer.calls == 2  # unchanged — reuse path


def test_run_precompute_regenerates_over_a_stored_placeholder(
    session: Session,
) -> None:
    """B043 F005 fix: a pre-B043 / LLM-down snapshot holds *placeholder*
    rationales for this as_of_date. The next run must REGENERATE them (not reuse
    the placeholder), so the LLM rationale actually lands after deploy instead of
    being frozen for the quarter."""

    # Seed the snapshot the way the pre-B043 precompute did: placeholder text.
    repo = RecommendationSnapshotRepository(session)
    repo.save_batch(
        as_of_date=date(2026, 3, 31),
        rows=[
            {
                "symbol": "AAPL",
                "sleeve": "satellite_us_quality",
                "target_weight": 0.2,
                "rationale": deterministic_rationale(
                    "satellite_us_quality", DATA_SOURCE_REAL
                ),
            },
            {
                "symbol": "SGOV",
                "sleeve": "risk_parity",
                "target_weight": 0.8,
                "rationale": deterministic_rationale("risk_parity", DATA_SOURCE_REAL),
            },
        ],
        master_meta={"data_source": DATA_SOURCE_REAL},
    )
    session.commit()

    explainer = _StubExplainer(_ok_result())
    run_precompute(session, score_fn=_fake_result, explainer=explainer)  # type: ignore[arg-type]
    assert explainer.calls == 2  # regenerated, did NOT reuse the placeholder
    rows = RecommendationSnapshotRepository(session).latest_snapshot()
    assert {r.rationale for r in rows} == {"grounded why"}


def test_run_precompute_degrades_to_placeholder_without_explainer(
    session: Session,
) -> None:
    summary = run_precompute(session, score_fn=_fake_result, explainer=None)
    assert summary.saved == 2
    rows = RecommendationSnapshotRepository(session).latest_snapshot()
    aapl = next(r for r in rows if r.symbol == "AAPL")
    assert aapl.rationale == deterministic_rationale(
        "satellite_us_quality", DATA_SOURCE_REAL
    )
