"""F003 G-B — as-of 正确性 + 修订不变性。

两条腿：
  (1) 真实数据：从 holdout 期次里找**实际存在多版本**的证券，
      构造修订前/修订后形成日，验证各自返回当时可见的那一版。
  (2) 修订不变性：注入一条未来修订后，旧形成日结果必须**逐字节不变**
      （对 ResolvedFact 做规范序列化后比 sha256）。
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import tushare as ts

from scripts.research.ashare_pit.codes import FactVersion
from scripts.research.ashare_pit.fetch import fetch_paged
from scripts.research.ashare_pit.resolver import build_versions, resolve_as_of
from scripts.research.ashare_pit.vintage_probe import FIELDS, load_token

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")


def fingerprint(fact) -> str:
    """ResolvedFact 的规范指纹——逐字节比较用。"""
    payload = {
        "status": str(fact.status),
        "value": str(fact.value),
        "formation_date": fact.formation_date,
        "selected": None
        if fact.selected is None
        else {
            "ts_code": fact.selected.ts_code,
            "end_date": fact.selected.end_date,
            "f_ann_date": fact.selected.f_ann_date,
            "ann_date": fact.selected.ann_date,
            "update_flag": fact.selected.update_flag,
            "value": str(fact.selected.value),
        },
        "candidates": [
            {"f_ann_date": c.f_ann_date, "value": str(c.value), "update_flag": c.update_flag}
            for c in fact.candidates
        ],
    }
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


# ---------- 真实修订案例：2021FY（F001 标为可信窗口，版本多重度 91.2%） ----------
pro = ts.pro_api(load_token())
PERIOD = "20211231"
df, report = fetch_paged(pro.income_vip, endpoint="income_vip", period=PERIOD, fields=FIELDS)
rows = df[df["report_type"] == "1"].to_dict("records")
print(f"{PERIOD}: pages={report.pages} rows={len(df)} consolidated={len(rows)}")

by_code = defaultdict(list)
for row in rows:
    by_code[row["ts_code"]].append(row)

# 真修订 = 同一证券在不同 f_ann_date 上有**不同的值**
revised = []
for code, items in by_code.items():
    versions = build_versions(items)
    by_date = defaultdict(set)
    for v in versions:
        by_date[v.f_ann_date].add(v.value)
    if len(by_date) >= 2 and len({v for s in by_date.values() for v in s}) >= 2:
        revised.append((code, versions))
revised.sort(key=lambda item: item[0])
print(f"真实修订证券数（同期多 f_ann_date 且值不同）= {len(revised)}")

results = []
for code, versions in revised[:12]:
    dates = sorted({v.f_ann_date for v in versions})
    first, last = dates[0], dates[-1]
    before = resolve_as_of(versions, first)          # 修订前形成日
    after = resolve_as_of(versions, last)            # 修订后形成日
    fp_before = fingerprint(before)

    # ★注入一条未来修订（f_ann_date 晚于 last，值改动）
    injected = [
        *versions,
        FactVersion(
            ts_code=code,
            end_date=PERIOD,
            f_ann_date="20991231",
            ann_date="20991231",
            update_flag="1",
            value=Decimal("-123456789.01"),
        ),
    ]
    before_after_injection = resolve_as_of(injected, first)
    fp_after_injection = fingerprint(before_after_injection)

    results.append(
        {
            "ts_code": code,
            "f_ann_dates": dates,
            "before_formation": first,
            "before_value": str(before.value),
            "before_status": str(before.status),
            "after_formation": last,
            "after_value": str(after.value),
            "after_status": str(after.status),
            "value_changed": before.value != after.value,
            "invariance_holds": fp_before == fp_after_injection,
            "superseded_flag_before": before.superseded_later,
        }
    )

n = len(results)
changed = sum(1 for r in results if r["value_changed"])
invariant = sum(1 for r in results if r["invariance_holds"])
supflag = sum(1 for r in results if r["superseded_flag_before"])
print(f"\n检验证券数 = {n}")
print(f"  修订前后取值不同           = {changed}/{n}")
print(f"  注入未来修订后旧形成日不变 = {invariant}/{n}")
print(f"  旧形成日正确置 superseded_later = {supflag}/{n}")
for r in results:
    print(f"  {r['ts_code']} {r['f_ann_dates']} {r['before_value']} -> {r['after_value']} "
          f"invariant={r['invariance_holds']}")

# ---------- H1：不得用 ann_date 代 f_ann_date ----------
# 构造修正行 ann_date 不变、f_ann_date 后移的情形，证明用 ann_date 会拿到错版本
v_first = FactVersion("TEST.SZ", "20211231", "20220330", "20220330", "0", Decimal("100"))
v_fix = FactVersion("TEST.SZ", "20211231", "20230415", "20220330", "1", Decimal("250"))
mid = "20220701"
by_fann = resolve_as_of([v_first, v_fix], mid)
by_anndate = resolve_as_of(
    [
        FactVersion(v.ts_code, v.end_date, v.ann_date, v.ann_date, v.update_flag, v.value)
        for v in (v_first, v_fix)
    ],
    mid,
)
print(f"\n[H1] f_ann_date 语义 -> {by_fann.value} (期望 100，当时可见的首版)")
print(f"[H1] 若误用 ann_date -> {by_anndate.status} / {by_anndate.value} "
      f"(证明用 ann_date 会污染：修正行伪装成首版当时即可见)")

(OUT / "gb-results.json").write_text(
    json.dumps(
        {
            "period": PERIOD,
            "n_revised_securities_in_period": len(revised),
            "checked": results,
            "h1_f_ann_date_value": str(by_fann.value),
            "h1_ann_date_status": str(by_anndate.status),
            "h1_ann_date_value": str(by_anndate.value),
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
