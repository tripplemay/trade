"""B109 F002 — as-of resolver 与分母的纯逻辑单测（离线，不联网）。

★所有 fixture 均为合成，但形态取自 B109 F001 探针实测的真实结构
（`docs/audits/B109-F001-vintage-probe-2026-07-20.md`）。
"""

from __future__ import annotations

from decimal import Decimal

from scripts.research.ashare_pit.codes import FactStatus, FactVersion, MarketCapStatus
from scripts.research.ashare_pit.marketcap import (
    build_point,
    identity_error,
    summarize,
)
from scripts.research.ashare_pit.resolver import (
    build_versions,
    dropped_row_count,
    resolve_as_of,
)


def _version(f_ann: str, value: str, *, ann: str = "20230422", flag: str = "1") -> FactVersion:
    return FactVersion(
        ts_code="000547.SZ",
        end_date="20221231",
        f_ann_date=f_ann,
        ann_date=ann,
        update_flag=flag,
        value=Decimal(value),
    )


# --- as-of 语义 ---


def test_returns_the_version_visible_at_formation_date() -> None:
    """探针实测的真实形态：首版 2023-04-22，修正在 2025-01-21 才可知。"""
    versions = [
        _version("20230422", "34679532.18", flag="0"),
        _version("20250121", "32973069.04", flag="1"),
    ]
    before = resolve_as_of(versions, "20240630")
    assert before.status is FactStatus.RESOLVED
    assert before.value == Decimal("34679532.18")
    assert before.superseded_later is True  # 后来被改过，必须暴露

    after = resolve_as_of(versions, "20250630")
    assert after.value == Decimal("32973069.04")
    assert after.superseded_later is False


def test_ann_date_must_not_be_used_as_the_knowledge_clock() -> None:
    """★修正行的 ann_date 与首版相同——用它做 as-of 会把修正值判为「当时就可见」。

    这里两行的 ann_date 都是 20230422，只有 f_ann_date 不同。
    若实现误用 ann_date，形成日 20240630 会拿到修正后的值。
    """
    versions = [
        _version("20230422", "34679532.18", ann="20230422", flag="0"),
        _version("20250121", "32973069.04", ann="20230422", flag="1"),
    ]
    assert resolve_as_of(versions, "20240630").value == Decimal("34679532.18")


def test_not_yet_published_is_distinct_from_missing() -> None:
    """形成日当时尚未披露是**经济事实**，不是数据缺失，覆盖漏斗必须分开计数。"""
    versions = [_version("20230422", "100")]
    assert resolve_as_of(versions, "20230101").status is FactStatus.NOT_YET_PUBLISHED
    assert resolve_as_of([], "20230101").status is FactStatus.FACT_MISSING


def test_conflicting_values_on_same_f_ann_date_fail_closed() -> None:
    """★占已知修订的 1.0%：同一 f_ann_date 上多个值，无法分辨先后。

    必须 fail closed，禁止按行序 / 抓取顺序 / update_flag 任选一条（上游禁令 #13）。
    """
    versions = [
        _version("20230422", "34679532.18", flag="0"),
        _version("20230422", "32973069.04", flag="1"),
    ]
    result = resolve_as_of(versions, "20240630")
    assert result.status is FactStatus.FACT_VERSION_AMBIGUOUS
    assert result.value is None
    assert len(result.candidates) == 2  # 候选全保留供人工裁定


def test_duplicate_rows_with_identical_value_are_not_ambiguous() -> None:
    """探针的第一个发现：flag=0/1 两行数值相同 = 重复行，不是冲突。"""
    versions = [
        _version("20230422", "34679532.18", flag="0"),
        _version("20230422", "34679532.18", flag="1"),
    ]
    assert resolve_as_of(versions, "20240630").status is FactStatus.RESOLVED


def test_future_versions_never_leak_into_the_result() -> None:
    """修订不变性：形成日之后的版本不得参与取值。"""
    base = [_version("20230422", "100")]
    baseline = resolve_as_of(base, "20240630").value
    with_future = resolve_as_of([*base, _version("20250101", "999")], "20240630")
    assert with_future.value == baseline
    assert with_future.superseded_later is True


# --- 规范化 ---


def test_rows_without_knowledge_clock_are_dropped_and_counted() -> None:
    """缺 f_ann_date 或缺值的行无法参与 as-of，丢弃但必须可计数（H4）。"""
    rows: list[dict[str, object]] = [
        {"ts_code": "A", "end_date": "20221231", "f_ann_date": "20230422", "n_income_attr_p": 1.0},
        {"ts_code": "A", "end_date": "20221231", "f_ann_date": "", "n_income_attr_p": 2.0},
        {"ts_code": "A", "end_date": "20221231", "f_ann_date": "20230422", "n_income_attr_p": None},
    ]
    versions = build_versions(rows)
    assert len(versions) == 1
    assert dropped_row_count(rows, versions) == 2


# --- 分母 ---


def test_identity_check_passes_on_consistent_basis() -> None:
    # close 元/股 × total_share 万股 = 万元，与 total_mv 同单位
    assert identity_error(Decimal("10"), Decimal("100"), Decimal("1000")) == Decimal(0)


def test_market_cap_converts_wan_to_cny_exactly_once() -> None:
    """★万元 → 元只在此转一次；下游不得再遇到万元。"""
    point = build_point(
        {
            "ts_code": "A",
            "trade_date": "20231229",
            "close": 10,
            "total_share": 100,
            "total_mv": 1000,
        }
    )
    assert point is not None
    assert point.status is MarketCapStatus.RESOLVED
    assert point.total_mv_wan == Decimal("1000")
    assert point.total_mv_cny == Decimal("10000000")


def test_identity_failure_is_isolated_not_silently_used() -> None:
    """股本口径不一致（例如供应商给的是流通股本）必须被身份校验拦下。"""
    point = build_point(
        {"ts_code": "A", "trade_date": "20231229", "close": 10, "total_share": 50, "total_mv": 1000}
    )
    assert point is not None
    assert point.status is MarketCapStatus.MARKET_CAP_IDENTITY_FAILED
    assert not point.is_usable
    assert point.is_severe_outlier


def test_non_positive_market_cap_is_rejected() -> None:
    """上游报告 §6：零或非正总市值一律拒绝。"""
    point = build_point(
        {"ts_code": "A", "trade_date": "20231229", "close": 10, "total_share": 100, "total_mv": 0}
    )
    assert point is not None
    assert point.status is MarketCapStatus.NON_POSITIVE_MARKET_CAP


def test_summary_counts_isolated_rows_explicitly() -> None:
    points = [
        build_point(
            {"ts_code": "A", "trade_date": "d", "close": 10, "total_share": 100, "total_mv": 1000}
        ),
        build_point(
            {"ts_code": "B", "trade_date": "d", "close": 10, "total_share": 50, "total_mv": 1000}
        ),
    ]
    report = summarize([p for p in points if p is not None])
    assert report["n"] == 2
    assert report["isolated"] == 1
    assert report["identity_pass_fraction"] == 0.5
