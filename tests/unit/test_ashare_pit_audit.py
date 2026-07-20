"""B109 F002 — Tushare vs 巨潮对拍器的纯逻辑单测（离线，不联网）。

被测的核心性质：**anchor 不可信时不得记到被审计方头上**，且一致率不得脱离
可裁定分母单独存在。
"""

from __future__ import annotations

from decimal import Decimal

from scripts.research.ashare_ep.codes import CrossCheckResult, FailureCode, Status
from scripts.research.ashare_pit.audit import (
    AuditVerdict,
    audit_summary,
    compare_one,
    select_audit_sample,
    to_ts_code,
)
from scripts.research.ashare_pit.codes import FactStatus, ResolvedFact


def _anchor(value: str | None, status: Status = Status.CONFIRMED) -> CrossCheckResult:
    return CrossCheckResult(
        status=status,
        value=Decimal(value) if value is not None else None,
        failure_code=None if status is Status.CONFIRMED else FailureCode.EXTRACTION_FAILED,
        sources=(),
    )


def _tushare(value: str | None, status: FactStatus = FactStatus.RESOLVED) -> ResolvedFact:
    return ResolvedFact(
        status=status,
        value=Decimal(value) if value is not None else None,
        selected=None,
        formation_date="20240630",
        candidates=(),
    )


def _case(
    anchor: CrossCheckResult,
    tushare: ResolvedFact,
    *,
    announcement_id: str = "A1",
) -> object:
    return compare_one(
        announcement_id=announcement_id,
        ts_code="000001.SZ",
        end_date="20221231",
        anchor=anchor,
        tushare=tushare,
    )


# --- 单份裁定 ---


def test_agreeing_values_match() -> None:
    case = _case(_anchor("45516000000"), _tushare("45516000000"))
    assert case.verdict is AuditVerdict.MATCH
    assert case.relative_error == Decimal(0)


def test_disagreeing_values_are_flagged_for_manual_adjudication() -> None:
    case = _case(_anchor("45516000000"), _tushare("45000000000"))
    assert case.verdict is AuditVerdict.MISMATCH
    assert case.is_adjudicable is True


def test_unusable_anchor_is_not_charged_against_tushare() -> None:
    """★方向反转的关键：巨潮 parser 抽不出值是 **parser** 的问题，不是 Tushare 错。"""
    case = _case(_anchor(None, Status.EXTRACTION_FAILED), _tushare("45516000000"))
    assert case.verdict is AuditVerdict.ANCHOR_UNUSABLE
    assert case.is_adjudicable is False


def test_single_source_anchor_is_rejected_as_truth() -> None:
    """★单源值正是 B108 实测错抽高发区（含 ×10⁴ 单位错绑）——不足以判 Tushare 的对错。"""
    anchor = CrossCheckResult(
        status=Status.SINGLE_SOURCE_UNCONFIRMED,
        value=Decimal("999"),
        failure_code=FailureCode.SINGLE_SOURCE_UNCONFIRMED,
        sources=(),
    )
    case = _case(anchor, _tushare("45516000000"))
    assert case.verdict is AuditVerdict.ANCHOR_UNUSABLE
    assert any("单源" in note for note in case.notes)


def test_anchor_has_value_but_tushare_does_not_counts_against_tushare() -> None:
    case = _case(_anchor("45516000000"), _tushare(None, FactStatus.FACT_VERSION_AMBIGUOUS))
    assert case.verdict is AuditVerdict.TUSHARE_UNRESOLVED
    assert case.is_adjudicable is True


def test_tolerance_absorbs_presentation_rounding_only() -> None:
    case = _case(_anchor("45516000000"), _tushare("45516040000"))  # 差 0.0000879
    assert case.verdict is AuditVerdict.MATCH
    far = _case(_anchor("45516000000"), _tushare("45570000000"))  # 差 0.00119
    assert far.verdict is AuditVerdict.MISMATCH


# --- 汇总的自欺陷阱 ---


def test_consistency_rate_never_appears_without_its_denominator() -> None:
    """★anchor 大面积失败时，一致率仍可能是 100%——必须并排给出可裁定占比。

    这里 8/10 的 anchor 不可用，剩 2 份全对。一致率 = 100% 但样本量只有 2。
    """
    cases = [_case(_anchor("100"), _tushare("100"), announcement_id=f"OK{i}") for i in range(2)]
    cases += [
        _case(_anchor(None, Status.EXTRACTION_FAILED), _tushare("100"), announcement_id=f"NA{i}")
        for i in range(8)
    ]
    summary = audit_summary(cases)

    assert summary["consistency_rate"] == 1.0
    assert summary["n_total"] == 10
    assert summary["n_adjudicable"] == 2
    assert summary["adjudicable_fraction"] == 0.2
    assert summary["consistency_denominator"] == "adjudicable_cases"


def test_summary_lists_every_case_needing_manual_adjudication() -> None:
    cases = [
        _case(_anchor("100"), _tushare("100"), announcement_id="A"),
        _case(_anchor("100"), _tushare("200"), announcement_id="B"),
        _case(_anchor("100"), _tushare(None, FactStatus.FACT_MISSING), announcement_id="C"),
    ]
    summary = audit_summary(cases)
    assert summary["consistency_rate"] == 1 / 3
    ids = [entry["announcement_id"] for entry in summary["requires_adjudication"]]
    assert ids == ["B", "C"]


def test_empty_audit_reports_none_not_a_fake_perfect_score() -> None:
    """零样本必须是 None，不是 1.0——「没测过」不得呈现为「全对」。"""
    summary = audit_summary([])
    assert summary["consistency_rate"] is None
    assert summary["adjudicable_fraction"] == 0.0


# --- 证券代码映射 ---


def test_exchange_suffix_is_derived_not_guessed() -> None:
    assert to_ts_code("600519") == "600519.SH"
    assert to_ts_code("688001") == "688001.SH"
    assert to_ts_code("000001") == "000001.SZ"
    assert to_ts_code("300142") == "300142.SZ"  # B108 语料里的真实代码


def test_out_of_universe_codes_return_none_rather_than_a_wrong_exchange() -> None:
    """★猜错交易所会让对拍悄悄比对两家公司——不报错，只表现为一个假「不一致」。"""
    assert to_ts_code("200011") is None  # B 股
    assert to_ts_code("830799") is None  # 北交所
    assert to_ts_code("60051") is None  # 位数不对
    assert to_ts_code("60A519") is None


# --- H3：Generator 不抽样 ---


def test_sample_selection_requires_an_explicit_seed() -> None:
    """★H3 由签名强制：没有默认 seed，Generator 无法「顺手」定下评测样本。"""
    import inspect

    signature = inspect.signature(select_audit_sample)
    assert signature.parameters["seed"].default is inspect.Parameter.empty
    assert signature.parameters["seed"].kind is inspect.Parameter.KEYWORD_ONLY
