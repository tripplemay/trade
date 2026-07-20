"""F003 G-A 补充 — 把 97 份「anchor 不可裁定」榨出信号。

严格区分效力：
  CONFIRMED(22)              → 计入 G-A 硬门（交叉确认的 anchor）
  SINGLE_SOURCE(58)          → **支持性证据**，不计入门（B108 实测单源是错抽高发区）
  SOURCE_CONFLICT(22)        → 看 Tushare 是否命中冲突候选之一 → 判是 parser 错还是 Tushare 错
  EXTRACTION_FAILED(17)      → 无信号
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from scripts.research.ashare_ep.crosscheck import cross_check
from scripts.research.ashare_pit.audit import relative_error

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
TXT_DIR = OUT / "txt"
detail = {d["announcement_id"]: d for d in json.loads((OUT / "audit-detail.json").read_text())}
anchors = json.loads((OUT / "anchors.json").read_text())

TOL = Decimal("0.001")
single_rows, conflict_rows = [], []

for rec in anchors:
    aid = rec["announcement_id"]
    d = detail.get(aid)
    if d is None or d["as_filed_value"] is None:
        continue
    tus = Decimal(d["as_filed_value"])
    text = (TXT_DIR / f"{aid}.txt").read_text(encoding="utf-8", errors="replace")
    result = cross_check(text)

    if rec["anchor_status"] == "SINGLE_SOURCE_UNCONFIRMED" and result.value is not None:
        err = relative_error(result.value, tus)
        single_rows.append(
            {**{k: d[k] for k in ("announcement_id", "ts_code", "end_date", "report_type")},
             "anchor": str(result.value), "tushare": str(tus), "rel_err": str(err),
             "agree": err <= TOL}
        )
    elif rec["anchor_status"] == "SOURCE_CONFLICT":
        cands = {str(s.value): s.source for s in result.sources}
        hit = [v for v in cands if relative_error(Decimal(v), tus) <= TOL]
        conflict_rows.append(
            {**{k: d[k] for k in ("announcement_id", "ts_code", "end_date", "report_type")},
             "tushare": str(tus), "candidates": cands,
             "tushare_matches_a_candidate": bool(hit),
             "matched_source": [cands[v] for v in hit]}
        )

(OUT / "supplement.json").write_text(
    json.dumps({"single_source": single_rows, "source_conflict": conflict_rows},
               ensure_ascii=False, indent=2), encoding="utf-8")

agree = sum(1 for r in single_rows if r["agree"])
print(f"[单源支持性证据] n={len(single_rows)} 一致={agree} ({agree / len(single_rows):.1%})"
      if single_rows else "[单源] 无")
for r in single_rows:
    if not r["agree"]:
        print("  DISAGREE", json.dumps(r, ensure_ascii=False))

hit = sum(1 for r in conflict_rows if r["tushare_matches_a_candidate"])
print(f"\n[冲突项] n={len(conflict_rows)} Tushare 命中某个候选={hit} "
      f"({hit / len(conflict_rows):.1%})" if conflict_rows else "[冲突] 无")
for r in conflict_rows:
    if not r["tushare_matches_a_candidate"]:
        print("  NO-HIT", json.dumps(r, ensure_ascii=False))
