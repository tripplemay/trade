"""B109 F002 — Tushare vs 巨潮原文的抽样对拍器。

复用 B108 的 `scripts/research/ashare_ep/` 框架，但**方向反转**：

===========  =====================  =====================
批次          truth anchor           被审计方
===========  =====================  =====================
B108          Tushare（参照）         巨潮 parser（被验收）
B109          巨潮原文（参照）         Tushare（被审计）
===========  =====================  =====================

B108 的真实产出不是 parser 本身，而是**交叉验证 / holdout / 结构化失败码**这套纪律。
巨潮 parser 已知在年报上只有 1/34 —— 但在**抽样对拍**场景下这不构成阻碍，因为：

1. anchor 抽不出值时判 ``ANCHOR_UNUSABLE``，**不计入 Tushare 的对错**；
2. 所有不一致项一律**人工裁定**（F003 的活）。

★★但这里埋着一个会让验收自欺的陷阱：anchor 失败率越高，可裁定分母越小，
「一致率」看起来就越漂亮。一份 90% 抽不出值的对拍报告完全可能给出「100% 一致」。
所以 :func:`audit_summary` **强制**同时输出 ``adjudicable_fraction``，
且一致率永远以可裁定项为分母、以 ``n_adjudicable`` 明示样本量——
不允许出现一个脱离分母单独引用的百分比。

★H3 纪律：本模块只提供抽样**能力**，Generator 不抽取 F003 的评测样本。
:func:`select_audit_sample` 的 ``seed`` 是**无默认值的必填参数**，由验收方自选。
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from scripts.research.ashare_ep.codes import CrossCheckResult, Status
from scripts.research.ashare_ep.sampling import Candidate, select_stratified
from scripts.research.ashare_pit.codes import FactStatus, ResolvedFact

# Tushare 值与巨潮原文的一致容差。两者指向同一个会计事实，差异只应来自
# 原文的呈现精度（多数公告以元或万元给到 2 位小数），故取紧容差。
DEFAULT_TOLERANCE = Decimal("0.001")


class AuditVerdict(StrEnum):
    """一份公告的对拍结论。"""

    MATCH = "MATCH"
    MISMATCH = "MISMATCH"
    """两边都有值但超出容差 → **人工裁定**（Tushare 错 / parser 错 / 口径差异）。"""

    TUSHARE_UNRESOLVED = "TUSHARE_UNRESOLVED"
    """被审计方没给出值。这**算 Tushare 的账**，计入可裁定分母。"""

    ANCHOR_UNUSABLE = "ANCHOR_UNUSABLE"
    """anchor 抽不出可信值 → 本例**无法裁定**，不计入一致率分母，但必须计数披露。"""


@dataclass(frozen=True)
class AuditCase:
    """一份公告的对拍记录。字段足以支撑人工复核，不需要回头再跑一遍。"""

    announcement_id: str
    ts_code: str
    end_date: str
    anchor_value: Decimal | None
    anchor_status: Status
    tushare_value: Decimal | None
    tushare_status: FactStatus
    relative_error: Decimal | None
    verdict: AuditVerdict
    notes: tuple[str, ...] = ()

    @property
    def is_adjudicable(self) -> bool:
        return self.verdict is not AuditVerdict.ANCHOR_UNUSABLE


def to_ts_code(sec_code: str) -> str | None:
    """巨潮的 6 位证券代码 → Tushare 的 ``ts_code``。无法归类返回 ``None``（不猜）。

    对拍的前提是两边指的是同一只证券。猜错交易所会让对拍悄悄比对两家公司——
    这种错配不会报错，只会表现为一个「不一致」，然后被人工裁定浪费掉。
    """
    code = sec_code.strip()
    if len(code) != 6 or not code.isdigit():
        return None
    if code.startswith(("600", "601", "603", "605", "688", "689")):
        return f"{code}.SH"
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return f"{code}.SZ"
    # 北交所 / B 股不在本项目宇宙内（上游报告 §2.1「暂不纳入」）
    return None


def relative_error(left: Decimal, right: Decimal) -> Decimal:
    """相对误差。分母做下限保护，避免零附近放大（同 B108 `crosscheck` 口径）。"""
    denominator = max(abs(left), abs(right), Decimal(1))
    return abs(left - right) / denominator


def compare_one(
    *,
    announcement_id: str,
    ts_code: str,
    end_date: str,
    anchor: CrossCheckResult,
    tushare: ResolvedFact,
    tolerance: Decimal = DEFAULT_TOLERANCE,
) -> AuditCase:
    """单份对拍。

    ★anchor 的可用性判据取 ``Status.CONFIRMED``（交叉确认过的值），
    **不接受** ``SINGLE_SOURCE_UNCONFIRMED``——单源值正是 B108 实测里错抽的高发区
    （F003 实测单源路径当场抓到 6 份错抽，含 ×10⁴ 单位错绑）。拿一个可能错的 anchor
    去判 Tushare 错，等于把 parser 的缺陷记到被审计方头上。
    """
    notes: list[str] = []

    if anchor.status is not Status.CONFIRMED or anchor.value is None:
        if anchor.status is Status.SINGLE_SOURCE_UNCONFIRMED:
            notes.append("anchor 仅单源，未交叉确认——不足以判定 Tushare 对错")
        return AuditCase(
            announcement_id=announcement_id,
            ts_code=ts_code,
            end_date=end_date,
            anchor_value=None,
            anchor_status=anchor.status,
            tushare_value=tushare.value,
            tushare_status=tushare.status,
            relative_error=None,
            verdict=AuditVerdict.ANCHOR_UNUSABLE,
            notes=(*notes, *anchor.notes),
        )

    if tushare.status is not FactStatus.RESOLVED or tushare.value is None:
        return AuditCase(
            announcement_id=announcement_id,
            ts_code=ts_code,
            end_date=end_date,
            anchor_value=anchor.value,
            anchor_status=anchor.status,
            tushare_value=None,
            tushare_status=tushare.status,
            relative_error=None,
            verdict=AuditVerdict.TUSHARE_UNRESOLVED,
            notes=(f"anchor 有值而被审计方无值（{tushare.status}）",),
        )

    error = relative_error(anchor.value, tushare.value)
    return AuditCase(
        announcement_id=announcement_id,
        ts_code=ts_code,
        end_date=end_date,
        anchor_value=anchor.value,
        anchor_status=anchor.status,
        tushare_value=tushare.value,
        tushare_status=tushare.status,
        relative_error=error,
        verdict=AuditVerdict.MATCH if error <= tolerance else AuditVerdict.MISMATCH,
        notes=tuple(notes),
    )


def audit_summary(cases: Iterable[AuditCase]) -> dict[str, object]:
    """对拍汇总。

    ★一致率**只以可裁定项为分母**，且与 ``adjudicable_fraction`` / ``n_adjudicable``
    绑定输出——见模块 docstring 的自欺陷阱。``n_total`` 是抽样份数，
    ``n_adjudicable`` 才是这个百分比背后真正的样本量。
    """
    items = list(cases)
    total = len(items)
    adjudicable = [item for item in items if item.is_adjudicable]
    matched = sum(1 for item in adjudicable if item.verdict is AuditVerdict.MATCH)

    counts = {verdict: 0 for verdict in AuditVerdict}
    for item in items:
        counts[item.verdict] += 1

    return {
        "n_total": total,
        "n_adjudicable": len(adjudicable),
        # anchor 覆盖率。这个数低 → 一致率的样本量小，两者必须并排读。
        "adjudicable_fraction": len(adjudicable) / total if total else 0.0,
        "consistency_rate": matched / len(adjudicable) if adjudicable else None,
        "consistency_denominator": "adjudicable_cases",
        **{f"count_{verdict.value.lower()}": counts[verdict] for verdict in AuditVerdict},
        # 需人工裁定的项——F003 必须逐条给出归因，不得只报一个比例
        "requires_adjudication": sorted(
            (
                {
                    "announcement_id": item.announcement_id,
                    "ts_code": item.ts_code,
                    "end_date": item.end_date,
                    "anchor_value": str(item.anchor_value),
                    "tushare_value": str(item.tushare_value),
                    "relative_error": str(item.relative_error),
                }
                for item in items
                if item.verdict in (AuditVerdict.MISMATCH, AuditVerdict.TUSHARE_UNRESOLVED)
            ),
            key=lambda entry: str(entry["announcement_id"]),
        ),
    }


def select_audit_sample(
    candidates: list[Candidate],
    *,
    seed: int,
    quota_per_stratum: int,
    exclude_ids: frozenset[str] = frozenset(),
) -> list[Candidate]:
    """抽取对拍样本（薄封装，复用 B108 的 seed 化分层抽样）。

    ★``seed`` **无默认值**是有意的：H3 要求 Generator 不得抽取 F003 的评测样本，
    而一个「合理的默认 seed」等价于替验收方选好了样本。同理本仓不预置任何 manifest。

    ``exclude_ids`` 供排除已烧掉的语料——B108 实测样本内 26.3% vs 样本外 16.7%，
    在见过的语料上测量会高估 57%。
    """
    return select_stratified(
        candidates,
        quota_per_stratum=quota_per_stratum,
        seed=seed,
        exclude_ids=exclude_ids,
    )
