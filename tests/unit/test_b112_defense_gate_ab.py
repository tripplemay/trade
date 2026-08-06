"""B112 F001 — 防御闸 A/B runner/报告的单测（含 H7 只算不裁的机器判据）。"""

from __future__ import annotations

import json
from datetime import date

import pytest

from scripts.research.b112_defense_gate_ab import _deltas
from scripts.research.b112_defense_gate_report import render

# --- _deltas 符号约定（判据输入的方向正确性）---


def _cell(full_mdd: float, oos_mdd: float, cagr: float, sharpe: float) -> dict:
    return {
        "segments": {
            "full": {
                "max_drawdown": full_mdd,
                "annualized_return": cagr,
                "sharpe_ratio": sharpe,
            },
            "oos": {
                "max_drawdown": oos_mdd,
                "annualized_return": cagr,
                "sharpe_ratio": sharpe,
            },
        }
    }


def test_deltas_positive_means_improvement() -> None:
    v0 = _cell(-0.58, -0.40, 0.13, 0.56)
    v1 = _cell(-0.40, -0.30, 0.12, 0.60)
    deltas = _deltas(v0, v1)
    # 回撤 −0.58→−0.40 = 改善 +18pp（正值）；CAGR −1pp；Sharpe +0.04。
    assert deltas["full"]["delta_max_drawdown_pp"] == pytest.approx(18.0)
    assert deltas["oos"]["delta_max_drawdown_pp"] == pytest.approx(10.0)
    assert deltas["full"]["delta_cagr_pp"] == pytest.approx(-1.0)
    assert deltas["full"]["delta_sharpe"] == pytest.approx(0.04)


def test_deltas_negative_when_gate_hurts() -> None:
    v0 = _cell(-0.30, -0.20, 0.13, 0.56)
    v1 = _cell(-0.45, -0.35, 0.10, 0.40)
    deltas = _deltas(v0, v1)
    assert deltas["full"]["delta_max_drawdown_pp"] == pytest.approx(-15.0)
    assert deltas["full"]["delta_cagr_pp"] == pytest.approx(-3.0)


# --- H7 机器判据：报告/产物无任何裁定措辞 ---

_FORBIDDEN = (
    "GO",
    "NO-GO",
    "NOGO",
    "INCONCLUSIVE",
    "值得投入",
    "有 edge",
    "有edge",
    "建议投入",
    "应当继续",
    "结论是",
)


def _sample_payload() -> dict:
    cell_v0 = {
        "segments": {
            "full": {
                "annualized_return": 0.131,
                "max_drawdown": -0.583,
                "sharpe_ratio": 0.56,
            },
            "oos": {
                "annualized_return": 0.284,
                "max_drawdown": -0.30,
                "sharpe_ratio": 0.93,
            },
        },
        "total_turnover": 12.3,
        "annual_turnover": 1.74,
        "total_cost": 4567.0,
        "rebalance_count": 88,
        "per_year_returns": {"2024": 0.15, "2025": -0.02},
        "gate_states": [],
    }
    cell_v1 = {
        "segments": {
            "full": {
                "annualized_return": 0.121,
                "max_drawdown": -0.40,
                "sharpe_ratio": 0.60,
            },
            "oos": {
                "annualized_return": 0.26,
                "max_drawdown": -0.22,
                "sharpe_ratio": 0.99,
            },
        },
        "total_turnover": 15.1,
        "annual_turnover": 2.14,
        "total_cost": 5100.0,
        "rebalance_count": 90,
        "per_year_returns": {"2024": 0.15, "2025": 0.01},
        "gate_states": [
            {
                "month": "2026-07",
                "active": True,
                "eval_date": "2026-06-30",
                "index_close": 3800.0,
                "ma_value": 4000.0,
                "reason": "on",
            }
        ],
    }
    comp = {"v0": cell_v0, "v1": cell_v1, "deltas": _deltas(cell_v0, cell_v1)}
    return {
        "honesty_statement": "只算不裁",
        "frozen_window": {"start": "2019-04-01", "end": "2026-07-31", "is_oos": "70/30"},
        "gate_caliber": "MA200",
        "criterion_thresholds": {
            "main_full_maxdd_improve_min_pp": 5.0,
            "main_oos_maxdd_improve_min_pp": 3.0,
            "secondary_delta_cagr_min_pp": -2.0,
            "secondary_delta_sharpe_min": -0.05,
            "note": "阈值为陈述值，独立于观测；施加与裁定归 F002（H7）。",
        },
        "input_coverage": {
            "universe": {
                "source": "测试",
                "n_blocks": 29,
                "block_sizes": {"2019-03-29": 800},
                "size_min": 799,
                "size_max": 800,
            },
            "prices": {
                "rows": 1000,
                "tickers": 1310,
                "date_min": "2018-01-02",
                "date_max": "2026-07-31",
                "segments": [
                    {
                        "name": "b081_prices_cache.pkl（测试段一）",
                        "rows": 700,
                        "span": "2018-01-02 → 2026-06-18",
                    },
                    {
                        "name": "b112_prices_ext.pkl（测试段二）",
                        "rows": 100,
                        "span": "2026-06-22 → 2026-07-31",
                    },
                    {
                        "name": "prices_newnames.pkl（测试段三）",
                        "rows": 200,
                        "span": "2018-01-01 → 2026-07-31",
                    },
                ],
                "dedupe_rule": "三段 concat 后按 (date, ticker) 去重（keep=first）",
                "splice": "段一 + 段二 + prices_newnames",
            },
            "index": {
                "series_days": 3000,
                "window_trading_days_total": 1780,
                "window_trading_days_covered": 1780,
            },
            "fundamentals": {
                "rows": 113064,
                "tickers": 2028,
                "nonnull_rates": {
                    "roe": 0.86,
                    "gross_margin": 0.99,
                    "fcf_yield": 0.50,
                    "debt_to_assets": 0.98,
                },
                "backfill_failures": 30,
                "note": "fcf_yield 缺口固有。",
            },
        },
        "comparisons": {
            "pure_momentum__100000": comp,
            "quality_momentum__100000": comp,
        },
        "generator_boundary": "判据的施加与裁定归 F002 的 Codex（铁律 #4）。",
    }


def test_render_has_no_verdict_language() -> None:
    md = render(_sample_payload())
    for word in _FORBIDDEN:
        assert word not in md, f"报告中出现结论性措辞: {word}"


def test_render_contains_criterion_table_and_gate_states() -> None:
    md = render(_sample_payload())
    assert "ΔMaxDD 全样本" in md
    assert "+18.30pp" in md  # −0.583→−0.40 的改善
    assert "防守月数 1" in md
    assert "2026-07" in md


def test_render_contains_coverage_and_annual_turnover() -> None:
    """F001-4/4a：报告必须含 H6 覆盖分母（三段价格披露）、OOS Sharpe 与年化换手（含公式）。"""
    md = render(_sample_payload())
    assert "覆盖分母" in md
    assert "prices_newnames" in md  # 新名段不得遗漏（4a）
    assert "Sharpe OOS" in md
    assert "年化换手" in md
    assert "交易日数/252" in md
    assert "29 个季度块" in md
    assert "1780/1780" in md  # 指数交易日覆盖口径（4a）


def test_runner_payload_has_no_verdict_language() -> None:
    payload = json.dumps(_sample_payload(), ensure_ascii=False, default=str)
    for word in _FORBIDDEN:
        assert word not in payload, f"产物中出现结论性措辞: {word}"


# --- F001-2 回归：原始 CSV 输入路径（无 pickle cache 掩盖）---


def test_load_fundamentals_frame_from_raw_csv(tmp_path) -> None:
    """F001-2 修复点：字符串 report_date 的原始 CSV 必须解析成 datetime 并补全
    schema 列，使 quality_score 直接可用（不经过任何 pickle 缓存）。"""

    from scripts.research.b112_defense_gate_ab import load_fundamentals_frame
    from trade.strategies.us_quality_momentum.factors import quality_score

    csv_path = tmp_path / "fundamentals.csv"
    csv_path.write_text(
        "report_date,ticker,fiscal_quarter,fiscal_quarter_end,roe,gross_margin,"
        "fcf_yield,debt_to_assets\n"
        "2024-04-30,600519.SH,2024Q1,2024-03-31,0.08,0.91,0.02,0.20\n"
        "2024-08-31,600519.SH,2024Q2,2024-06-30,0.09,0.91,0.03,0.19\n"
        "2024-04-30,000858.SZ,2024Q1,2024-03-31,0.06,0.75,0.01,0.30\n",
        encoding="utf-8",
    )
    frame = load_fundamentals_frame(csv_path)
    assert str(frame["report_date"].dtype).startswith("datetime64")
    for column in ("pe", "pb", "ev_ebitda", "earnings_yield"):
        assert column in frame.columns  # NaN-filled schema
    # 不抛 TypeError 且按 PIT 取到最新可见行。
    scores = quality_score(frame, date(2024, 5, 15))
    assert not scores.empty
