from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/test/ashare_dividend_ep_data_readiness.py"
SPEC = importlib.util.spec_from_file_location("ashare_dividend_ep_data_readiness", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
research = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = research
SPEC.loader.exec_module(research)


def _top10_body(update_date: str = "2026-07-10") -> dict[str, object]:
    return {
        "success": True,
        "data": {
            "updateDate": update_date,
            "weightList": [
                {
                    "indexCode": "H30269",
                    "securityCode": f"6000{number:02d}",
                    "tradeDate": "20260710",
                    "weight": number / 10,
                }
                for number in range(10)
            ],
        },
    }


def test_parse_csi_top10_validates_exact_index_and_count() -> None:
    result = research.parse_csi_top10(_top10_body())
    assert result["update_date"] == "2026-07-10"
    assert len(result["rows"]) == 10

    bad = _top10_body()
    bad["data"]["weightList"][0]["indexCode"] = "OTHER"
    with pytest.raises(ValueError, match="code mismatch"):
        research.parse_csi_top10(bad)


def test_request_validated_retries_an_empty_success_response() -> None:
    class Response:
        def __init__(self, content: bytes) -> None:
            self.content = content
            self.text = content.decode()

        def raise_for_status(self) -> None:
            return None

    class Session:
        def __init__(self) -> None:
            self.responses = [Response(b""), Response(b"20260630")]

        def get(self, *_args: object, **_kwargs: object) -> Response:
            return self.responses.pop(0)

    response = research.request_validated(
        Session(),
        "https://example.test",
        attempts=2,
        validator=lambda item: len(item.text) == 8,
    )
    assert response.text == "20260630"


def test_summarize_official_sheet_pins_current_50_and_weight_sum() -> None:
    frame = pd.DataFrame(
        {
            "日期Date": [20260630] * 50,
            "指数代码 Index Code": ["H30269"] * 50,
            "成份券代码Constituent Code": range(50),
            "权重(%)weight": [2.0] * 50,
        }
    )
    result = research.summarize_official_sheet(frame, include_weight=True)
    assert result["rows"] == 50
    assert result["as_of_date"] == "2026-06-30"
    assert result["weight_sum_pct"] == pytest.approx(100.0)


def test_summarize_fundamentals_exposes_deadline_and_non_ttm_shape() -> None:
    frame = pd.DataFrame(
        {
            "report_date": ["2020-04-30", "2020-04-30", "2020-08-31"],
            "ticker": ["A", "A", "B"],
            "fiscal_quarter": ["2019Q4", "2020Q1", "2020Q2"],
            "fiscal_quarter_end": ["2019-12-31", "2020-03-31", "2020-06-30"],
            "pe": [10.0, 10.0, 20.0],
            "earnings_yield": [0.10, 0.025, 0.025],
        }
    )
    result = research.summarize_fundamentals(frame)
    assert result["report_month_days"] == ["04-30", "08-31"]
    assert result["duplicate_ticker_report_date_rows"] == 2
    assert result["ep_to_inverse_pe_median_ratio_by_quarter"]["Q1"] == pytest.approx(0.25)
    assert result["parent_net_profit_column_present"] is False


def test_visible_ep_coverage_uses_only_data_available_by_rebalance() -> None:
    universe = pd.DataFrame(
        {
            "as_of_date": ["2020-03-31", "2020-03-31", "2020-06-30", "2020-06-30"],
            "ticker": ["A", "B", "A", "B"],
        }
    )
    fundamentals = pd.DataFrame(
        {
            "report_date": ["2020-01-01", "2020-05-01"],
            "ticker": ["A", "B"],
            "earnings_yield": [0.05, 0.04],
        }
    )
    result = research.visible_ep_coverage(universe, fundamentals)
    assert result["union_coverage"] == 1.0
    assert result["per_date"][0]["coverage"] == 0.5
    assert result["per_date"][1]["coverage"] == 1.0


def test_raw_report_coverage_requires_fresh_notice_and_matching_period() -> None:
    reports = pd.DataFrame(
        {
            "SECUCODE": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "REPORTDATE": ["2020-03-31", "2020-03-31", "2020-03-31"],
            "NOTICE_DATE": ["2020-04-01", "2021-04-01", "2020-04-02"],
        }
    )
    universe = pd.DataFrame(
        {
            "as_of_date": ["2020-03-31", "2020-03-31"],
            "ticker": ["000001.SZ", "000002.SZ"],
        }
    )
    rows, summary = research.raw_report_coverage(reports, universe)
    assert rows[0]["covered"] == 1
    assert summary["min"] == 0.5


def test_component_discovery_excludes_plain_index_point_series(tmp_path: Path) -> None:
    (tmp_path / "index_h30269.csv").write_text("date,close\n", encoding="utf-8")
    (tmp_path / "h30269_weights.csv").write_text("date,weight\n", encoding="utf-8")
    result = research.discover_h30269_component_files(tmp_path)
    assert len(result) == 1
    assert result[0].endswith("h30269_weights.csv")


def _gate_inputs() -> dict[str, object]:
    return {
        "history_validation": {"complete_2013_2026": True},
        "fundamentals": {
            "parent_net_profit_column_present": True,
            "total_market_cap_column_present": True,
        },
        "h30269_ep_coverage_min": 0.95,
        "raw_reports": {
            "archived_as_filed_values_available": True,
            "notice_crosscheck": {"comparable": 10, "match_rate": 1.0},
        },
        "prices": {
            "first_date": "2013-01-01",
            "corporate_action_fields_present": True,
        },
        "size": {"standard_ep_total_market_cap_available": True},
        "pit_industry_available": True,
        "all_inputs_reproducible": True,
    }


def test_data_gates_fail_closed_and_control_backtest_permission() -> None:
    inputs = _gate_inputs()
    result = research.evaluate_data_gates(**inputs)
    assert result["verdict"] == "DATA_GO"
    assert result["portfolio_backtest_allowed"] is True

    inputs["pit_industry_available"] = False
    inputs["history_validation"] = {"complete_2013_2026": False}
    inputs["h30269_ep_coverage_min"] = 0.9499
    failed = research.evaluate_data_gates(**inputs)
    assert failed["verdict"] == "DATA_NO_GO"
    assert failed["gates"]["pit_industry_for_each_h30269_rebalance_available"] is False
    assert failed["gates"][
        "h30269_pit_ep_coverage_each_rebalance_at_least_95pct"
    ] is False
