"""F003 H1 — 分解「改用 ann_date 会怎样」：静默错值 vs fail-closed。"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import tushare as ts

from scripts.research.ashare_pit.fetch import fetch_paged
from scripts.research.ashare_pit.resolver import build_versions, resolve_as_of
from scripts.research.ashare_pit.vintage_probe import FIELDS, load_token

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
pro = ts.pro_api(load_token())
df, _ = fetch_paged(pro.income_vip, endpoint="income_vip", period="20211231", fields=FIELDS)
rows = df[df["report_type"] == "1"].to_dict("records")
by_code = defaultdict(list)
for r in rows:
    by_code[r["ts_code"]].append(r)

FORMATION = "20220630"
kinds = Counter()
examples = []
for code, items in by_code.items():
    vf = build_versions(items)
    if not vf:
        continue
    va = [type(v)(v.ts_code, v.end_date, v.ann_date, v.ann_date, v.update_flag, v.value)
          for v in vf if v.ann_date]
    if not va:
        continue
    a = resolve_as_of(vf, FORMATION)
    b = resolve_as_of(va, FORMATION)
    if str(a.status) == str(b.status) and a.value == b.value:
        kinds["identical"] += 1
        continue
    if str(a.status) == "RESOLVED" and str(b.status) == "RESOLVED" and a.value != b.value:
        kinds["SILENT_WRONG_VALUE"] += 1
        if len(examples) < 8:
            examples.append({"ts_code": code, "f_ann_semantics": str(a.value),
                             "ann_date_semantics": str(b.value),
                             "selected_f_ann": a.selected.f_ann_date if a.selected else None})
    else:
        kinds[f"{a.status}->{b.status}"] += 1

print("形成日", FORMATION, "2021FY")
for k, v in kinds.most_common():
    print(f"  {k}: {v}")
print("\n静默错值样例:")
for e in examples:
    print(" ", json.dumps(e, ensure_ascii=False))
(OUT / "h1-decomposition.json").write_text(
    json.dumps({"formation_date": FORMATION, "kinds": dict(kinds), "examples": examples},
               ensure_ascii=False, indent=2), encoding="utf-8")
