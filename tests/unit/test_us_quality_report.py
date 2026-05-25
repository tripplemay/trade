"""Unit tests for the B025 backtest report serializer."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from trade.backtest.us_quality_momentum.engine import run_backtest
from trade.backtest.us_quality_momentum.report import (
    BILINGUAL_DISCLAIMER,
    METRIC_LABELS_BILINGUAL,
    build_report_payload,
    render_markdown,
    write_reports,
)

BACKTEST_START = date(2017, 1, 1)
BACKTEST_END = date(2024, 12, 31)


@pytest.fixture(scope="module")
def fixture_backtest_result():
    return run_backtest(start=BACKTEST_START, end=BACKTEST_END)


def test_build_report_payload_contains_required_sections(fixture_backtest_result) -> None:
    payload = build_report_payload(fixture_backtest_result)
    required = {
        "disclaimer",
        "strategy",
        "config",
        "window",
        "metrics",
        "monthly_returns",
        "annual_returns",
        "average_sector_exposure",
        "average_ticker_contribution",
        "benchmarks",
        "data_source",
    }
    assert required.issubset(payload.keys())


def test_build_report_payload_disclaimer_is_bilingual(fixture_backtest_result) -> None:
    payload = build_report_payload(fixture_backtest_result)
    assert payload["disclaimer"] == BILINGUAL_DISCLAIMER
    assert "research-only" in str(payload["disclaimer"])
    assert "仅供研究使用" in str(payload["disclaimer"])


def test_build_report_payload_metrics_include_all_required_keys(
    fixture_backtest_result,
) -> None:
    payload = build_report_payload(fixture_backtest_result)
    metrics = payload["metrics"]
    assert set(METRIC_LABELS_BILINGUAL).issubset(metrics)


def test_build_report_payload_records_parameters_hash(fixture_backtest_result) -> None:
    payload = build_report_payload(fixture_backtest_result)
    assert len(payload["strategy"]["parameters_hash"]) == 64


def test_render_markdown_includes_bilingual_disclaimer_in_header(
    fixture_backtest_result,
) -> None:
    payload = build_report_payload(fixture_backtest_result)
    markdown = render_markdown(payload)
    head = "\n".join(markdown.splitlines()[:6])
    # Disclaimer appears within the first six lines of the report.
    assert BILINGUAL_DISCLAIMER in head
    assert "美股质量动量回测" in head


def test_render_markdown_contains_all_metric_rows(fixture_backtest_result) -> None:
    payload = build_report_payload(fixture_backtest_result)
    markdown = render_markdown(payload)
    for label in METRIC_LABELS_BILINGUAL.values():
        assert label in markdown


def test_render_markdown_shows_bilingual_section_titles(fixture_backtest_result) -> None:
    payload = build_report_payload(fixture_backtest_result)
    markdown = render_markdown(payload)
    for section in ("Strategy / 策略", "Window / 回测窗口", "Performance Metrics / 业绩指标"):
        assert section in markdown


def test_write_reports_emits_json_and_markdown_files(
    fixture_backtest_result, tmp_path: Path
) -> None:
    artifacts = write_reports(fixture_backtest_result, output_dir=tmp_path)
    assert artifacts.json_path.exists()
    assert artifacts.markdown_path.exists()
    assert artifacts.json_path.suffix == ".json"
    assert artifacts.markdown_path.suffix == ".md"


def test_write_reports_json_is_valid_and_round_trips(
    fixture_backtest_result, tmp_path: Path
) -> None:
    artifacts = write_reports(fixture_backtest_result, output_dir=tmp_path)
    loaded = json.loads(artifacts.json_path.read_text(encoding="utf-8"))
    assert loaded["disclaimer"] == BILINGUAL_DISCLAIMER
    assert "strategy" in loaded


def test_write_reports_filename_uses_as_of_when_provided(
    fixture_backtest_result, tmp_path: Path
) -> None:
    custom_as_of = date(2024, 6, 30)
    artifacts = write_reports(
        fixture_backtest_result, as_of=custom_as_of, output_dir=tmp_path
    )
    assert artifacts.json_path.name == "2024-06-30.json"
    assert artifacts.markdown_path.name == "2024-06-30.md"


def test_benchmarks_section_present_when_enabled(fixture_backtest_result) -> None:
    payload = build_report_payload(fixture_backtest_result, with_benchmarks=True)
    benchmarks = payload["benchmarks"]
    assert {"spy_proxy", "qqq_proxy", "rsp_proxy", "static_top_n"}.issubset(benchmarks)
    for entry in benchmarks.values():
        assert "ending_value" in entry
        assert "cumulative_return" in entry
        assert "excess_return_total_bps" in entry


def test_benchmarks_section_can_be_disabled(fixture_backtest_result) -> None:
    payload = build_report_payload(fixture_backtest_result, with_benchmarks=False)
    assert payload["benchmarks"] == {}
