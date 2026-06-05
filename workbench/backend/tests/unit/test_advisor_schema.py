"""B036 F001 — advisor output parsing + citation contract validation."""

from __future__ import annotations

import json

import pytest

from workbench_api.advisor.grounding import Grounding, GroundingNewsItem
from workbench_api.advisor.schema import (
    parse_advice_output,
    references_valid,
)


def _grounding() -> Grounding:
    return Grounding(
        sleeve="satellite_us_quality",
        quant_present=True,
        quant_signal_sha="sha256:abc",
        quant_signal_payload="payload",
        news=[
            GroundingNewsItem(url="https://a.example/1", title="A", published_at="2026-06-01"),
            GroundingNewsItem(url="https://b.example/2", title="B", published_at="2026-06-02"),
        ],
        market_context=[],
    )


def _advice(sha: str = "sha256:abc", urls: list[str] | None = None) -> str:
    return json.dumps(
        {
            "advice": "Stay diversified within the sleeve.",
            "rationale": "Grounded in the provided signal + news.",
            "references": [
                {"quant_signal_sha": sha, "news_urls": urls if urls is not None else ["https://a.example/1"]}
            ],
        }
    )


def test_parse_valid_output() -> None:
    out = parse_advice_output(_advice())
    assert out.advice.startswith("Stay diversified")
    assert out.references[0].quant_signal_sha == "sha256:abc"
    assert out.references[0].news_urls == ["https://a.example/1"]


def test_parse_tolerates_markdown_code_fence() -> None:
    # haiku-4.5 wraps the JSON in a ```json fence despite the prompt
    # (verified live 2026-06-05); a compliant answer must still parse.
    fenced = f"```json\n{_advice()}\n```"
    out = parse_advice_output(fenced)
    assert out.references[0].quant_signal_sha == "sha256:abc"


def test_parse_non_json_raises() -> None:
    with pytest.raises(ValueError, match="not JSON"):
        parse_advice_output("I cannot help with that.")


def test_parse_missing_key_raises() -> None:
    with pytest.raises(ValueError, match="missing key"):
        parse_advice_output(json.dumps({"advice": "x", "rationale": "y"}))


def test_parse_references_must_be_list() -> None:
    with pytest.raises(ValueError, match="'references' must be a list"):
        parse_advice_output(json.dumps({"advice": "x", "rationale": "y", "references": {}}))


def test_references_valid_when_in_input_set() -> None:
    assert references_valid(parse_advice_output(_advice()), _grounding()) is True


def test_references_invalid_when_empty() -> None:
    out = parse_advice_output(
        json.dumps({"advice": "x", "rationale": "y", "references": []})
    )
    assert references_valid(out, _grounding()) is False


def test_references_invalid_on_sha_mismatch() -> None:
    out = parse_advice_output(_advice(sha="sha256:FORGED"))
    assert references_valid(out, _grounding()) is False


def test_references_invalid_on_out_of_set_url() -> None:
    out = parse_advice_output(_advice(urls=["https://evil.example/x"]))
    assert references_valid(out, _grounding()) is False
