from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/test/ashare_dividend_value_first_look.py"
SPEC = importlib.util.spec_from_file_location("ashare_dividend_value_first_look", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
research = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = research
SPEC.loader.exec_module(research)


def test_parse_product_records_requires_exact_target_etf() -> None:
    records = [
        {
            "productCode": "563700",
            "fundName": "红利价值ETF",
            "fundType": "ETF",
            "indexCode": "H30270",
            "inceptionDate": "2025-04-16",
            "exchange": "上海证券交易所",
            "aum": "4.08",
        },
        {
            "productCode": "024564",
            "fundName": "红利价值ETF联接",
            "fundType": "联接基金",
            "indexCode": "H30270",
            "inceptionDate": "2025-07-29",
            "exchange": "-",
        },
    ]
    product = research.parse_product_records(records, "H30270", "563700")
    assert product["product_code"] == "563700"
    assert product["fund_type"] == "ETF"

    with pytest.raises(ValueError, match="expected one ETF"):
        research.parse_product_records(records, "H30269", "563700")


def _tencent_body(rows: int = 60) -> dict[str, object]:
    dates = pd.bdate_range(end="2026-06-30", periods=rows)
    return {
        "data": {
            "sh563700": {
                "day": [
                    [date.date().isoformat(), "1", "1", "1", "1", "100"]
                    for date in dates
                ]
            }
        }
    }


def test_parse_tencent_daily_validates_end_and_positive_rows() -> None:
    frame = research.parse_tencent_daily(
        _tencent_body(), "sh563700", "2026-06-30"
    )
    assert len(frame) == 60
    assert frame.index[-1] == pd.Timestamp("2026-06-30")

    with pytest.raises(ValueError, match="last row"):
        research.parse_tencent_daily(_tencent_body(), "sh563700", "2026-06-29")


def test_product_diagnostics_converts_board_lots_and_marks_short_history() -> None:
    daily = research.parse_tencent_daily(
        _tencent_body(), "sh563700", "2026-06-30"
    )
    product = {
        "product_code": "563700",
        "fund_type": "ETF",
        "index_code": "H30270",
        "inception_date": "2025-04-16",
    }
    listing = {"listing_date": "2025-04-28"}
    sse = pd.DataFrame(
        {
            "close": [1.0] * len(daily),
            "volume_shares": [10_000.0] * len(daily),
            "trade_amount_cny": [10_000.0] * len(daily),
        },
        index=daily.index,
    )
    result = research.product_diagnostics(product, listing, daily, sse)
    assert result["live_full_months"] == 14
    assert result["adv_cny_sse_official"] == pytest.approx(10_000.0)
    assert result["target_participation_of_adv"] == pytest.approx(210.0)


def test_parse_sse_listing_pins_target_index_and_date() -> None:
    body = {
        "result": [
            {
                "fundCode": "563700",
                "listingDate": "20250428",
                "INDEX_CODE": "H30270",
                "INDEX_NAME": "中证红利价值指数",
                "secNameFull": "红利价值ETF易方达",
                "companyName": "易方达基金管理有限公司",
            }
        ]
    }
    listing = research.parse_sse_listing(body, "563700")
    assert listing["listing_date"] == "2025-04-28"
    assert listing["index_code"] == "H30270"


def test_parse_sse_trade_record_converts_official_units() -> None:
    body = {
        "result": [
            {
                "TX_DATE": "20260630",
                "SEC_CODE": "563700",
                "CLOSE_PRICE": "0.986",
                "TRADE_VOL": "938.72",
                "TRADE_AMT": "920.82",
            }
        ]
    }
    row = research.parse_sse_trade_record(body, "563700", "2026-06-30")
    assert row["volume_shares"] == pytest.approx(9_387_200.0)
    assert row["trade_amount_cny"] == pytest.approx(9_208_200.0)


def _passing_index_inputs() -> tuple[
    dict[str, object], dict[str, object], list[dict[str, float]], dict[str, object]
]:
    post = {
        "baseline": {"months": 100},
        "delta": {
            "cagr": 0.03,
            "sharpe_rf0": 0.20,
            "max_drawdown_improvement": -0.02,
        },
    }
    inference = {
        "newey_west_hac": {"t": 2.0},
        "block_bootstrap_95": {"annualized_lower": 0.01},
    }
    folds = [{"cagr_delta": 0.01}] * 3 + [{"cagr_delta": -0.01}]
    defense = {
        "2022": {
            "available": True,
            "delta": {"max_drawdown_improvement": -0.019},
        }
    }
    return post, inference, folds, defense


def test_index_gate_uses_frozen_return_priority_thresholds() -> None:
    post, inference, folds, defense = _passing_index_inputs()
    result = research.evaluate_index_gates(post, inference, folds, defense)
    assert result["all_pass"] is True

    post["delta"]["cagr"] = 0.019
    failed = research.evaluate_index_gates(post, inference, folds, defense)
    assert failed["all_pass"] is False
    assert failed["gates"]["cagr_delta_at_least_2pp"] is False


def test_index_gate_allows_at_most_three_point_drawdown_deterioration() -> None:
    post, inference, folds, defense = _passing_index_inputs()
    post["delta"]["max_drawdown_improvement"] = -0.03
    assert research.evaluate_index_gates(post, inference, folds, defense)[
        "gates"
    ]["max_drawdown_deterioration_within_3pp"] is True
    post["delta"]["max_drawdown_improvement"] = -0.030001
    assert research.evaluate_index_gates(post, inference, folds, defense)[
        "gates"
    ]["max_drawdown_deterioration_within_3pp"] is False


def test_window_diagnostics_include_previous_close_anchor() -> None:
    frame = pd.DataFrame(
        {
            "baseline": [100.0, 90.0, 80.0],
            "candidate": [100.0, 95.0, 100.0],
        },
        index=pd.to_datetime(["2021-12-31", "2022-01-04", "2022-01-05"]),
    )
    result = research.anchored_window_diagnostics(frame, "2022-01-01", "2022-12-31")
    assert result["anchor_date"] == "2021-12-31"
    assert result["baseline"]["return"] == pytest.approx(-0.20)
    assert result["baseline"]["max_drawdown"] == pytest.approx(-0.20)
    assert result["candidate"]["return"] == pytest.approx(0.0)


def test_implementation_gate_requires_history_and_one_percent_adv() -> None:
    product = {
        "product_code": "563700",
        "fund_type": "ETF",
        "index_code": "H30270",
    }
    diagnostics = {
        "live_full_months": 60,
        "target_participation_of_adv": 0.01,
    }
    assert research.evaluate_implementation_gates(product, diagnostics)[
        "all_pass"
    ] is True

    diagnostics["live_full_months"] = 14
    diagnostics["target_participation_of_adv"] = 0.22
    failed = research.evaluate_implementation_gates(product, diagnostics)
    assert failed["verdict"] == "IMPLEMENTATION_NO_GO"
    assert failed["gates"]["live_product_history_at_least_60_months"] is False
    assert failed["gates"]["target_capital_at_most_1pct_adv"] is False


@pytest.mark.parametrize(
    ("index_verdict", "implementation_verdict", "expected"),
    [
        ("NO_GO", "IMPLEMENTATION_NO_GO", "NO_GO"),
        ("GO", "IMPLEMENTATION_NO_GO", "PAPER_ONLY"),
        ("GO", "GO", "GO"),
    ],
)
def test_overall_verdict_precedence(
    index_verdict: str, implementation_verdict: str, expected: str
) -> None:
    assert research.derive_overall_verdict(
        {"verdict": index_verdict}, {"verdict": implementation_verdict}
    ) == expected
