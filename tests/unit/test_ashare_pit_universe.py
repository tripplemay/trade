"""B109 F002 — PIT 证券宇宙的纯逻辑单测（离线，不联网）。

核心被测性质是**禁令 #11**：历史截面必须包含日后退市的公司。
"""

from __future__ import annotations

from scripts.research.ashare_pit.universe import (
    UniverseStatus,
    build_name_records,
    build_securities,
    name_as_of,
    summarize_universe,
    universe_as_of,
    universe_status,
)


def _security(
    ts_code: str,
    *,
    list_date: str,
    delist_date: str = "",
    list_status: str = "L",
    name: str = "某公司",
) -> dict[str, object]:
    return {
        "ts_code": ts_code,
        "symbol": ts_code[:6],
        "name": name,
        "list_status": list_status,
        "list_date": list_date,
        "delist_date": delist_date,
    }


# --- 成分 as-of / 幸存者偏差 ---


def test_delisted_company_is_in_the_universe_before_it_delisted() -> None:
    """★禁令 #11 的核心：2021 年退市的公司在 2015 年的截面里必须存在。

    若实现按 ``list_status == 'D'`` 排除，这条会失败——那正是幸存者偏差的来源。
    """
    securities = build_securities(
        [_security("000001.SZ", list_date="19910403", delist_date="20210430", list_status="D")]
    )
    assert universe_status(securities[0], "20150630") is UniverseStatus.IN_UNIVERSE
    assert universe_status(securities[0], "20211231") is UniverseStatus.ALREADY_DELISTED
    # 退市当日即出局（delist_date <= 形成日）
    assert universe_status(securities[0], "20210430") is UniverseStatus.ALREADY_DELISTED


def test_not_yet_listed_company_is_excluded() -> None:
    securities = build_securities([_security("688001.SH", list_date="20190722")])
    assert universe_status(securities[0], "20180630") is UniverseStatus.NOT_YET_LISTED
    assert universe_status(securities[0], "20190930") is UniverseStatus.IN_UNIVERSE


def test_missing_list_date_is_not_silently_included() -> None:
    """无上市日 → 不猜、不默认纳入，落在自己的状态码上（H4）。"""
    securities = build_securities([_security("900001.SH", list_date="")])
    assert universe_status(securities[0], "20200630") is UniverseStatus.LIST_DATE_MISSING
    assert universe_as_of(securities, "20200630") == []


def test_universe_as_of_is_sorted_and_mixes_live_and_doomed_names() -> None:
    securities = build_securities(
        [
            _security("000002.SZ", list_date="19910129"),
            _security("000001.SZ", list_date="19910403", delist_date="20210430", list_status="D"),
            _security("300001.SZ", list_date="20091030"),
        ]
    )
    codes = [item.ts_code for item in universe_as_of(securities, "20150630")]
    assert codes == ["000001.SZ", "000002.SZ", "300001.SZ"]


def test_summary_exposes_how_many_current_members_delist_later() -> None:
    """这个字段是禁令 #11 的自查探针：久远截面里它若为 0，几乎必是只拉了 L。"""
    securities = build_securities(
        [
            _security("000001.SZ", list_date="19910403", delist_date="20210430", list_status="D"),
            _security("000002.SZ", list_date="19910129"),
        ]
    )
    summary = summarize_universe(securities, "20150630")
    assert summary["in_universe"] == 2
    assert summary["in_universe_delisted_later"] == 1
    assert summary["count_already_delisted"] == 0


# --- 名称 as-of / 前视泄漏 ---


def test_name_as_of_returns_the_historical_name_not_the_current_one() -> None:
    """★一家 2020 年才被 ST 的公司，2015 年的截面不得显示 *ST 名称。"""
    records = build_name_records(
        [
            {"ts_code": "000001.SZ", "name": "平安银行", "start_date": "20120802", "end_date": ""},
            {
                "ts_code": "000004.SZ",
                "name": "国农科技",
                "start_date": "20140620",
                "end_date": "20200430",
            },
            {"ts_code": "000004.SZ", "name": "*ST国农", "start_date": "20200501", "end_date": ""},
        ]
    )
    assert name_as_of(records, "000004.SZ", "20150630") == "国农科技"
    assert name_as_of(records, "000004.SZ", "20201231") == "*ST国农"


def test_name_as_of_returns_none_when_uncovered_rather_than_guessing() -> None:
    """无覆盖记录返回 None——调用方不得回退到 stock_basic 的当前名称（前视）。"""
    records = build_name_records(
        [{"ts_code": "000004.SZ", "name": "国农科技", "start_date": "20140620", "end_date": ""}]
    )
    assert name_as_of(records, "000004.SZ", "20130101") is None
    assert name_as_of(records, "999999.SZ", "20200101") is None


def test_overlapping_name_records_take_the_latest_effective_one() -> None:
    records = build_name_records(
        [
            {"ts_code": "000004.SZ", "name": "旧名", "start_date": "20140620", "end_date": ""},
            {"ts_code": "000004.SZ", "name": "新名", "start_date": "20180101", "end_date": ""},
        ]
    )
    assert name_as_of(records, "000004.SZ", "20200101") == "新名"


def test_name_records_without_start_date_are_dropped() -> None:
    records = build_name_records(
        [{"ts_code": "000004.SZ", "name": "无区间", "start_date": "", "end_date": ""}]
    )
    assert records == []
