"""B108 F001 — 多源交叉验证（spec §3.2）。公开入口在本模块。

判定规则：

.. code-block:: text

    S1 与 S2 都抽到且相对误差 <= 0.1%   → CONFIRMED
    仅一个源抽到                        → SINGLE_SOURCE_UNCONFIRMED
    S1 与 S2 都抽到但超出容差           → SOURCE_CONFLICT（返回 None + 全部候选）
    S3 与已 CONFIRMED 值数量级不符      → MAGNITUDE_IMPLAUSIBLE（撤销 CONFIRMED）
    无源抽到                            → EXTRACTION_FAILED

**冲突时返回 None，不返回猜测值。** 这是本批次的核心行为改变：原实现无论抽对抽错
都返回同样形状的数据，调用方无从分辨；现在抽不准就说抽不准。
"""

from __future__ import annotations

from decimal import Decimal

from scripts.research.ashare_ep.codes import (
    CrossCheckResult,
    FailureCode,
    SourceValue,
    Status,
)
from scripts.research.ashare_ep.sources import (
    extract_basic_eps,
    extract_s1,
    extract_s2,
    magnitude_is_plausible,
    parse_document,
)

# S1/S2 一致性容差。两个来源引用的是同一个会计事实，差异只应来自四舍五入呈现，
# 因此容差取得很紧；放松容差会让交叉验证失去发现单位/列位错误的能力。
DEFAULT_TOLERANCE = Decimal("0.001")


def relative_error(left: Decimal, right: Decimal) -> Decimal:
    """相对误差。分母做下限保护，避免零附近放大。"""
    denominator = max(abs(left), abs(right), Decimal(1))
    return abs(left - right) / denominator


def _agree(values: list[SourceValue], tolerance: Decimal) -> bool:
    return all(
        relative_error(left.value, right.value) <= tolerance
        for index, left in enumerate(values)
        for right in values[index + 1 :]
    )


def cross_check(
    text: str,
    *,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> CrossCheckResult:
    """对一份 ``pdftotext -layout`` 文本做归母净利润的多源交叉验证。"""
    rows = parse_document(text)
    s1_values, s1_failures = extract_s1(text.splitlines(), rows)
    s2_values, s2_failures = extract_s2(text.splitlines(), rows)

    notes: list[str] = []
    for failure in (*s1_failures, *s2_failures):
        notes.append(str(failure))

    found = [*s1_values, *s2_values]
    if not found:
        return CrossCheckResult(
            status=Status.EXTRACTION_FAILED,
            value=None,
            failure_code=(
                FailureCode.LABEL_NOT_FOUND
                if all(code is FailureCode.LABEL_NOT_FOUND for code in (*s1_failures, *s2_failures))
                else FailureCode.EXTRACTION_FAILED
            ),
            sources=(),
            notes=tuple(notes),
        )

    # 同一来源命中多行且值不一致，本身就是冲突信号（例如合并表与母公司表被同时匹配）
    if not _agree(s1_values, tolerance) or not _agree(s2_values, tolerance):
        return CrossCheckResult(
            status=Status.SOURCE_CONFLICT,
            value=None,
            failure_code=FailureCode.SOURCE_CONFLICT,
            sources=tuple(found),
            notes=(*notes, "同一来源内部多行取值不一致"),
        )

    basic_eps = extract_basic_eps(text.splitlines(), rows)

    if not s1_values or not s2_values:
        # ★E05 修复：单源路径同样要过 S3 哨兵。
        #
        # 原实现在这里直接 return，哨兵只在 CONFIRMED 路径上跑，对 39.5% 的单源结果
        # 结构性不可达——而单源恰恰是最需要兜底的一类（没有第二个来源可对照）。
        # B108 F003 实测：接上哨兵当场能抓到 6 份错抽，含 002670 的 ×10⁴ 单位错绑。
        single = found[0]
        if magnitude_is_plausible(single.value, basic_eps) is False:
            return CrossCheckResult(
                status=Status.MAGNITUDE_IMPLAUSIBLE,
                value=None,
                failure_code=FailureCode.MAGNITUDE_IMPLAUSIBLE,
                sources=tuple(found),
                notes=(*notes, f"单源值未过数量级哨兵（基本EPS={basic_eps}）"),
            )
        return CrossCheckResult(
            status=Status.SINGLE_SOURCE_UNCONFIRMED,
            value=single.value,
            failure_code=FailureCode.SINGLE_SOURCE_UNCONFIRMED,
            sources=tuple(found),
            notes=tuple(notes),
        )

    if not _agree([s1_values[0], s2_values[0]], tolerance):
        return CrossCheckResult(
            status=Status.SOURCE_CONFLICT,
            value=None,
            failure_code=FailureCode.SOURCE_CONFLICT,
            sources=tuple(found),
            notes=(
                *notes,
                f"S1={s1_values[0].value} S2={s2_values[0].value} "
                f"相对误差={relative_error(s1_values[0].value, s2_values[0].value)}",
            ),
        )

    confirmed = s1_values[0].value

    # S3 哨兵：只否决，不确认
    plausible = magnitude_is_plausible(confirmed, basic_eps)
    if plausible is False:
        return CrossCheckResult(
            status=Status.MAGNITUDE_IMPLAUSIBLE,
            value=None,
            failure_code=FailureCode.MAGNITUDE_IMPLAUSIBLE,
            sources=tuple(found),
            notes=(*notes, f"推算股本超出可信区间（基本EPS={basic_eps}）"),
        )
    if plausible is None:
        notes.append("S3 哨兵不适用（基本EPS 缺失或过于接近零）")

    return CrossCheckResult(
        status=Status.CONFIRMED,
        value=confirmed,
        failure_code=None,
        sources=tuple(found),
        notes=tuple(notes),
    )
