"""B110 F002 — 面板 CLI 的**纯逻辑**单元测试（离线，不联网）。

★诚实边界：``run()`` 与 ``load_token()`` 是联网/凭据路径，**本文件不测**。
按 B109 `test_ashare_pit_vintage_probe.py` 立下的规矩，测不到的路径要标注为
「未验证」而不是假装验证过。这些路径由 F002 的真实数据跑与 F004 的独立复算覆盖。

本文件覆盖的是几个**会静默改变结果**的纯函数：

1. **期次范围 54 期而非 48**：形成日 `20130131` 的 Q3 锚点需要 `C_Q3(2011)`。
2. ★**"nan" 归一**：缺失值经 ``astype(str)`` 变成字面量 `"nan"`，它不是空串，
   与日期做字典序比较时 `"n" > "2"` → 该行被当成「尚未披露」而不是「无值」。
3. ★**`report_type` 占比闸门**：裸 `== "1"` 在 dtype 漂成 int64 时会整期静默归零，
   返回空表而不是报错——不进 `failures`，漏斗看起来一切正常。
4. ★**证券视图不实体化**：144 月 × 5,000 只 × 54 期建字典是 4×10⁷ 次插入。
"""

from __future__ import annotations

import pandas as pd
import pytest

from scripts.research.ashare_pit.codes import FactVersion
from scripts.research.ashare_pit.ep_panel_cli import (
    CONSOLIDATED,
    Ledger,
    _filter_report_type,
    _next_month,
    _normalize,
    _SecurityPeriodView,
    _versions_index,
    quarter_ends,
)
from scripts.research.ashare_pit.fetch import FetchReport
from scripts.research.ashare_pit.pipeline import month_end_dates

# --- 期次与网格算术 ---


def test_period_range_covers_2011q3_through_2024fy() -> None:
    """★54 期不是 48 期。滑窗 5 期会让每年 1-3 月的形成日系统性 null，且只打早年。"""
    periods = quarter_ends()
    assert len(periods) == 54
    assert periods[0] == "20110930"
    assert periods[-1] == "20241231"
    assert periods == sorted(periods)


def test_the_formation_grid_is_144_and_the_price_grid_is_145() -> None:
    """★144 个形成日需要 t+1 月末价 → 价格网格必须多一格，否则最后一格无收益。"""
    assert len(month_end_dates("201301", "202412")) == 144
    assert len(month_end_dates("201301", _next_month("202412"))) == 145


def test_next_month_rolls_the_year() -> None:
    assert _next_month("202412") == "202501"
    assert _next_month("202401") == "202402"


# --- ★缺失值归一 ---


def test_literal_nan_strings_are_normalized_to_empty() -> None:
    """★`"nan"` 不是空串。放它进 f_ann_date，该行会被误判为「尚未披露」。"""
    frame = pd.DataFrame({"f_ann_date": ["20240420", "nan", "None"], "v": ["1", "2", "3"]})
    normalized = _normalize(frame)
    assert list(normalized["f_ann_date"]) == ["20240420", "", ""]


def test_a_row_whose_announcement_date_is_null_is_dropped_not_treated_as_future() -> None:
    rows = _normalize(
        pd.DataFrame(
            {
                "ts_code": ["A", "B"],
                "end_date": ["20231231", "20231231"],
                "f_ann_date": ["20240420", "nan"],
                "ann_date": ["20240420", "nan"],
                "update_flag": ["0", "0"],
                "n_income_attr_p": ["100", "200"],
            }
        )
    ).to_dict("records")
    index = _versions_index(rows)
    assert set(index) == {"A"}


# --- ★report_type 占比闸门 ---


def test_the_report_type_filter_strips_and_compares_as_string() -> None:
    frame = pd.DataFrame({"report_type": [" 1 ", "1", "2"], "v": [1, 2, 3]})
    assert len(_filter_report_type(frame, CONSOLIDATED, "20231231")) == 2


def test_an_abnormally_small_consolidated_share_raises_instead_of_returning_empty() -> None:
    """★整期静默归零是最坏的失败形态：不报错、不进 failures、漏斗看着正常。"""
    frame = pd.DataFrame({"report_type": ["2"] * 100 + ["1"] * 5, "v": range(105)})
    with pytest.raises(RuntimeError, match="占比异常"):
        _filter_report_type(frame, CONSOLIDATED, "20231231")


def test_an_empty_frame_passes_through_without_a_false_alarm() -> None:
    assert _filter_report_type(pd.DataFrame(), CONSOLIDATED, "20231231").empty


# --- 证券视图 ---


def _version(code: str) -> FactVersion:
    from decimal import Decimal

    return FactVersion(
        ts_code=code,
        end_date="20231231",
        f_ann_date="20240420",
        ann_date="20240420",
        update_flag="0",
        value=Decimal("1"),
    )


def test_the_security_view_reads_lazily_and_returns_empty_for_absent_codes() -> None:
    index = {"20231231": {"A": [_version("A")]}}
    view = _SecurityPeriodView(index, "A", ("20231231", "20230930"))
    assert len(view.get("20231231", [])) == 1
    assert view.get("20230930", []) == []
    other = _SecurityPeriodView(index, "B", ("20231231",))
    assert other.get("20231231", []) == []


def test_the_security_view_iterates_the_declared_periods() -> None:
    view = _SecurityPeriodView({}, "A", ("20231231", "20230930"))
    assert list(view) == ["20231231", "20230930"]
    assert len(view) == 2


# --- 成本留痕（spec §8 硬性）---


def test_the_ledger_sums_pages_and_rows_across_endpoints() -> None:
    ledger = Ledger()
    first = FetchReport(endpoint="income_vip", params={}, pages=3, rows=12000)
    second = FetchReport(endpoint="daily_basic", params={}, pages=2, rows=5300)
    second.truncation_suspected = True
    second.failures.append("daily_basic:offset=5000")
    ledger.add(first)
    ledger.add(second)
    summary = ledger.as_dict()
    assert summary["api_calls_total"] == 5
    assert summary["api_rows_total"] == 17300
    assert summary["truncation_suspected"] == ["daily_basic"]
    assert summary["failures"] == ["daily_basic:offset=5000"]


def test_an_empty_ledger_reports_zero_not_an_absent_key() -> None:
    summary = Ledger().as_dict()
    assert summary["api_calls_total"] == 0
    assert summary["truncation_suspected"] == []
