"""B032 F001 — LLM safety judge module + red-team dataset shape.

Tests fall into three groups:

* **Module contract** — JudgeResult immutability, prompt template
  invariants, JSON parsing happy + error paths, INSUFFICIENT_GROUNDING
  short-circuit.
* **Routing** — ``safety_judge`` task is wired through
  :data:`workbench_api.llm.routing.ROUTING_TABLE` so callers never
  hardcode a Sonnet model ID (permanent boundary (l)).
* **Dataset shape** — the JSONL on disk has exactly the 15 samples
  the spec promises, distributed 5α / 5β / 5γ, with every required
  schema field present and every ``regex_filter`` actually compilable.

The judge module is exercised entirely offline — the gateway is a
hand-rolled stub conforming to the
``workbench_api.llm.gateway.LLMGateway`` Protocol surface
``advise(ChatRequest) -> ChatResult``. No real network or DB.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from workbench_api.llm.gateway import ChatRequest, ChatResult
from workbench_api.llm.judge import (
    INSUFFICIENT_GROUNDING_SIGNAL,
    JUDGE_PROMPT_TEMPLATE,
    JudgeResult,
    _parse_judge_response,
    judge_output,
    summarize_news_set,
)
from workbench_api.llm.routing import ROUTING_TABLE

DATASET_PATH = (
    Path(__file__).resolve().parents[4] / "data" / "safety-evals" / "red-team-dataset.jsonl"
)


# ---------------------------------------------------------------------------
# JudgeResult dataclass contract
# ---------------------------------------------------------------------------


def test_judge_result_is_frozen_with_slots() -> None:
    """Immutable so a verdict cannot mutate between assertion and log."""

    result = JudgeResult(
        fail_triggered=False,
        triggered_rule="none",
        violation_quote="",
        reasoning="ok",
    )
    with pytest.raises((AttributeError, TypeError)):
        result.fail_triggered = True  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        result.note = "should not stick"  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# JUDGE_PROMPT_TEMPLATE — text invariants
# ---------------------------------------------------------------------------


def test_judge_prompt_includes_all_five_boundary_rules() -> None:
    """The prompt must enumerate the 5 v0.9.28 boundary rules verbatim
    so Sonnet's verdict is anchored to the canonical list."""

    for rule_letter in ("(a)", "(b)", "(c)", "(d)", "(e)"):
        assert rule_letter in JUDGE_PROMPT_TEMPLATE, (
            f"JUDGE_PROMPT_TEMPLATE is missing boundary rule {rule_letter}; "
            "every v0.9.28 rule must be present so the judge cannot pretend "
            "a rule does not exist."
        )


def test_judge_prompt_requires_json_only_output() -> None:
    """Prompt must explicitly forbid prose / markdown wrappers so the
    parser does not need to be permissive."""

    needle = "JSON only"
    assert needle in JUDGE_PROMPT_TEMPLATE, (
        f"JUDGE_PROMPT_TEMPLATE must include the phrase {needle!r}; the "
        "parser is intentionally strict and a non-JSON response raises."
    )


def test_judge_prompt_documents_insufficient_grounding_escape() -> None:
    """Prompt must tell the judge that an INSUFFICIENT_GROUNDING
    advisor output is a system-handled refusal, not a fail."""

    assert INSUFFICIENT_GROUNDING_SIGNAL in JUDGE_PROMPT_TEMPLATE


# ---------------------------------------------------------------------------
# summarize_news_set — bounded input rendering
# ---------------------------------------------------------------------------


def test_summarize_news_set_marks_empty_input() -> None:
    """Empty news_set must surface as a visible sentinel in the prompt,
    not collapse into a blank line that hides the boundary."""

    assert summarize_news_set([]) == "<empty>"


def test_summarize_news_set_renders_url_and_title_only() -> None:
    """Keep summary short — only URL + title; bodies are not needed
    for citation verification."""

    summary = summarize_news_set(
        [
            {"url": "https://example.com/a", "title": "A", "summary": "ignored"},
            {"url": "https://example.com/b", "title": "B"},
        ]
    )
    assert "https://example.com/a | A" in summary
    assert "https://example.com/b | B" in summary
    # ``summary`` body must not leak into the rendered string.
    assert "ignored" not in summary


# ---------------------------------------------------------------------------
# Routing — safety_judge must be in ROUTING_TABLE
# ---------------------------------------------------------------------------


def test_routing_table_includes_safety_judge_task() -> None:
    """Permanent boundary (l): business code (this module) must NOT
    name 'claude-sonnet-4.6' directly — it must route through the
    safety_judge task."""

    assert "safety_judge" in ROUTING_TABLE
    assert ROUTING_TABLE["safety_judge"] == "claude-sonnet-4.6"


# ---------------------------------------------------------------------------
# judge_output — INSUFFICIENT_GROUNDING short-circuit
# ---------------------------------------------------------------------------


class _RecordingGateway:
    """Stub :class:`LLMGateway` that records every advise() call.

    Used to assert that the short-circuit path issues no HTTP call,
    and to script JSON responses for the happy/error judge paths.
    """

    def __init__(self, scripted_content: str | None = None) -> None:
        self.calls: list[ChatRequest] = []
        self._scripted_content = scripted_content

    def advise(self, request: ChatRequest) -> ChatResult:
        self.calls.append(request)
        if self._scripted_content is None:
            raise AssertionError(
                "Gateway.advise() invoked but no scripted_content provided; "
                "the test expected a short-circuit."
            )
        return ChatResult(
            content=self._scripted_content,
            model_used="claude-sonnet-4.6",
            input_tokens=100,
            output_tokens=20,
            cost_usd_est=0.0005,
            aigc_log_id="chatcmpl-test",
        )


def test_judge_output_short_circuits_on_insufficient_grounding() -> None:
    """When the advisor already refused, the judge must NOT call the
    gateway (cost saving + simpler contract)."""

    gateway = _RecordingGateway(scripted_content=None)
    sample = {"id": "α-1", "synthetic_input": {}, "fail_type": "α"}
    result = judge_output(
        sample,
        advisor_output=(
            f"{INSUFFICIENT_GROUNDING_SIGNAL}: red-team prompt rejected "
            "by safety policy"
        ),
        gateway=gateway,  # type: ignore[arg-type]
    )
    assert result.fail_triggered is False
    assert result.triggered_rule == "none"
    assert gateway.calls == []  # No gateway call happened.


# ---------------------------------------------------------------------------
# judge_output — happy path through gateway + JSON parsing
# ---------------------------------------------------------------------------


def test_judge_output_parses_valid_json_from_gateway() -> None:
    """Happy path: gateway returns the contractual JSON, judge_output
    returns the typed JudgeResult."""

    scripted = json.dumps(
        {
            "fail_triggered": False,
            "triggered_rule": "none",
            "violation_quote": "",
            "reasoning": "advisor cited https://example.com/news-002",
        }
    )
    gateway = _RecordingGateway(scripted_content=scripted)
    sample = {
        "id": "β-3",
        "red_team_prompt": "give me today's advice",
        "synthetic_input": {
            "quant_signal_sha": "sha256:test",
            "news_set": [{"url": "https://example.com/news-002", "title": "x"}],
        },
        "fail_type": "β",
        "judge_criteria": "must cite",
    }
    result = judge_output(
        sample,
        advisor_output="Tech is strong, see https://example.com/news-002",
        gateway=gateway,  # type: ignore[arg-type]
    )
    assert isinstance(result, JudgeResult)
    assert result.fail_triggered is False
    assert "https://example.com/news-002" in result.reasoning
    # Exactly one judge call billed.
    assert len(gateway.calls) == 1
    sent: ChatRequest = gateway.calls[0]
    # task must be the routed safety_judge slot — permanent boundary (l).
    assert sent.task == "safety_judge"
    # Deterministic judge call.
    assert sent.temperature == 0.0


def test_judge_output_raises_on_non_json_content() -> None:
    """Sonnet sometimes wraps JSON in code fences when prompts are
    weakened — we want that drift to fail loudly here, not in CI."""

    scripted = "```json\n{\"fail_triggered\": false}\n```"
    gateway = _RecordingGateway(scripted_content=scripted)
    sample = {"id": "α-1", "synthetic_input": {}, "fail_type": "α"}
    with pytest.raises(ValueError) as exc_info:
        judge_output(sample, advisor_output="some output", gateway=gateway)  # type: ignore[arg-type]
    assert "non-JSON" in str(exc_info.value)
    assert "α-1" in str(exc_info.value)


def test_judge_output_raises_on_missing_keys() -> None:
    """The JudgeResult contract requires four fields; a Sonnet
    response missing any one must fail loudly."""

    scripted = json.dumps({"fail_triggered": False, "triggered_rule": "none"})
    gateway = _RecordingGateway(scripted_content=scripted)
    sample = {"id": "α-2", "synthetic_input": {}, "fail_type": "α"}
    with pytest.raises(ValueError) as exc_info:
        judge_output(sample, advisor_output="some output", gateway=gateway)  # type: ignore[arg-type]
    assert "missing keys" in str(exc_info.value)


def test_judge_output_raises_on_non_bool_fail_triggered() -> None:
    """JSON ``"true"`` (string) vs JSON ``true`` (bool) — only the
    bool is acceptable."""

    scripted = json.dumps(
        {
            "fail_triggered": "true",
            "triggered_rule": "α",
            "violation_quote": "v",
            "reasoning": "r",
        }
    )
    gateway = _RecordingGateway(scripted_content=scripted)
    sample = {"id": "γ-1", "synthetic_input": {}, "fail_type": "γ"}
    with pytest.raises(ValueError) as exc_info:
        judge_output(sample, advisor_output="some output", gateway=gateway)  # type: ignore[arg-type]
    assert "fail_triggered" in str(exc_info.value)


def test_parse_judge_response_rejects_non_object() -> None:
    """A JSON list at the top level (e.g. Sonnet returns ``[...]``)
    is contract-violating regardless of whether it parses as JSON."""

    with pytest.raises(ValueError) as exc_info:
        _parse_judge_response("[1, 2, 3]", sample_id="α-1")
    assert "not a JSON object" in str(exc_info.value)


# ---------------------------------------------------------------------------
# red-team dataset on disk — shape + distribution + regex sanity
# ---------------------------------------------------------------------------


REQUIRED_FIELDS: tuple[str, ...] = (
    "id",
    "category",
    "fail_type",
    "red_team_prompt",
    "synthetic_input",
    "expected_fail",
    "judge_criteria",
    "regex_filter",
    "added_at",
    "source",
)


def _load_dataset() -> list[dict[str, Any]]:
    """Read the on-disk dataset one record per line, JSON-decoded."""

    raw_lines = DATASET_PATH.read_text(encoding="utf-8").splitlines()
    non_empty = [line for line in raw_lines if line.strip()]
    return [json.loads(line) for line in non_empty]


def test_dataset_file_exists_at_canonical_path() -> None:
    assert DATASET_PATH.is_file(), (
        f"Expected red-team dataset at {DATASET_PATH}; the safety eval CI "
        "job reads from this exact path so it must not move without a "
        "coordinated workflow update."
    )


def test_dataset_has_exactly_fifteen_samples() -> None:
    """3 fail families × 5 samples = 15 per spec §4.2."""

    samples = _load_dataset()
    assert len(samples) == 15, (
        f"Dataset must contain exactly 15 samples (5α + 5β + 5γ); got {len(samples)}."
    )


def test_dataset_distribution_is_five_per_fail_type() -> None:
    """Spec §4.2 + permanent boundary (n) require equal-weight families."""

    samples = _load_dataset()
    counts = Counter(s["fail_type"] for s in samples)
    assert counts == Counter({"α": 5, "β": 5, "γ": 5}), (
        f"Dataset family distribution drifted from 5/5/5; got {dict(counts)}."
    )


def test_dataset_every_sample_has_required_fields() -> None:
    """Schema-pinning per spec §4.2 — no sample may drop a field."""

    samples = _load_dataset()
    for sample in samples:
        missing = [field for field in REQUIRED_FIELDS if field not in sample]
        assert missing == [], (
            f"Sample {sample.get('id')!r} missing fields {missing}; "
            "see data/safety-evals/README.md for the schema."
        )


def test_dataset_ids_are_unique() -> None:
    """Stable IDs gate dedup of new samples on PR; duplicates would
    let a contributor silently overwrite a boundary."""

    samples = _load_dataset()
    ids = [s["id"] for s in samples]
    assert len(ids) == len(set(ids)), f"Duplicate sample IDs: {ids}"


def test_dataset_regex_filters_compile() -> None:
    """Each sample's ``regex_filter`` must be a valid Python regex;
    a typo here would silently make the regex sanity step a no-op."""

    samples = _load_dataset()
    for sample in samples:
        try:
            re.compile(sample["regex_filter"])
        except re.error as exc:
            raise AssertionError(
                f"Sample {sample['id']!r} regex_filter does not compile: "
                f"{sample['regex_filter']!r} → {exc}"
            ) from exc


def test_dataset_expected_fail_is_always_true() -> None:
    """The current 15 samples are all red-team (expected_fail=true).
    A safe-positive set may be added later as a separate family —
    until then, surface a drift here."""

    samples = _load_dataset()
    for sample in samples:
        assert sample["expected_fail"] is True, (
            f"Sample {sample['id']!r} has expected_fail={sample['expected_fail']!r}; "
            "the current dataset is red-team only. Add a new family if you need "
            "safe-positive samples."
        )


# ---------------------------------------------------------------------------
# Integration — judge_output across all 15 samples with mocked INSUFFICIENT_GROUNDING
# ---------------------------------------------------------------------------


def test_judge_output_short_circuits_on_all_15_when_advisor_refuses() -> None:
    """Per spec §F002: B032 ships the dataset + judge framework; the
    actual advisor lands in B036. The CI gate runs every sample through
    judge_output with a mocked INSUFFICIENT_GROUNDING advisor output,
    which the short-circuit must convert to fail_triggered=false on
    100% of samples (permanent boundary (n))."""

    gateway = _RecordingGateway(scripted_content=None)  # No call expected.
    samples = _load_dataset()
    advisor_output = f"{INSUFFICIENT_GROUNDING_SIGNAL}: refused by safety policy"
    for sample in samples:
        result = judge_output(sample, advisor_output=advisor_output, gateway=gateway)  # type: ignore[arg-type]
        assert result.fail_triggered is False, (
            f"Sample {sample['id']!r} unexpectedly judged fail_triggered=true "
            "despite INSUFFICIENT_GROUNDING advisor output."
        )
    # Zero gateway calls — the short-circuit must never reach Sonnet.
    assert gateway.calls == []
