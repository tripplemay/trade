"""F003 G-A — 对拍：巨潮原文（anchor）vs Tushare as-of（被审计方）。

两个口径并排跑，供人工裁定用：
  as_filed  = resolve_as_of(formation_date = 该公告披露日)  ← 主口径（PIT 语义）
  latest    = resolve_as_of(formation_date = 99991231)      ← 参照（看不一致是否源于修订）
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from scripts.research.ashare_ep.codes import CrossCheckResult, Status
from scripts.research.ashare_pit.audit import audit_summary, compare_one
from scripts.research.ashare_pit.resolver import build_versions, resolve_as_of

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
anchors = json.loads((OUT / "anchors.json").read_text())
rows_by_period = json.loads((OUT / "tushare-rows.json").read_text())

STATUS_BY_NAME = {s.value: s for s in Status}


def versions_for(period: str, ts_code: str):
    rows = [r for r in rows_by_period.get(period, []) if r.get("ts_code") == ts_code]
    return build_versions(rows)


cases = []
detail = []
for rec in anchors:
    ts_code = rec.get("ts_code")
    formation = rec.get("formation_date")
    if ts_code is None or formation is None:
        continue
    versions = versions_for(rec["end_date"], ts_code)
    as_filed = resolve_as_of(versions, formation)
    latest = resolve_as_of(versions, "99991231")

    anchor = CrossCheckResult(
        status=STATUS_BY_NAME[rec["anchor_status"]],
        value=Decimal(rec["anchor_value"]) if rec["anchor_value"] is not None else None,
        failure_code=None,
        sources=(),
        notes=tuple(rec.get("notes", [])),
    )
    case = compare_one(
        announcement_id=rec["announcement_id"],
        ts_code=ts_code,
        end_date=rec["end_date"],
        anchor=anchor,
        tushare=as_filed,
    )
    cases.append(case)
    detail.append(
        {
            "announcement_id": rec["announcement_id"],
            "ts_code": ts_code,
            "end_date": rec["end_date"],
            "report_type": rec["report_type"],
            "formation_date": formation,
            "anchor_status": rec["anchor_status"],
            "anchor_value": rec["anchor_value"],
            "as_filed_status": str(as_filed.status),
            "as_filed_value": str(as_filed.value) if as_filed.value is not None else None,
            "as_filed_f_ann": as_filed.selected.f_ann_date if as_filed.selected else None,
            "latest_status": str(latest.status),
            "latest_value": str(latest.value) if latest.value is not None else None,
            "latest_f_ann": latest.selected.f_ann_date if latest.selected else None,
            "n_versions": len(versions),
            "superseded_later": as_filed.superseded_later,
            "verdict": str(case.verdict),
            "relative_error": str(case.relative_error) if case.relative_error else None,
        }
    )

summary = audit_summary(cases)
(OUT / "audit-summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
(OUT / "audit-detail.json").write_text(
    json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8"
)

print("n_total           =", summary["n_total"])
print("n_adjudicable     =", summary["n_adjudicable"])
print("adjudicable_frac  = {:.1%}".format(summary["adjudicable_fraction"]))
cr = summary["consistency_rate"]
print("consistency_rate  =", f"{cr:.2%}" if cr is not None else None)
for key in sorted(k for k in summary if k.startswith("count_")):
    print(f"  {key} = {summary[key]}")
print("\n需人工裁定项:")
for item in summary["requires_adjudication"]:
    print(" ", json.dumps(item, ensure_ascii=False))
