"""B108 F003 — Evaluator 侧结果分层汇总。"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path


def main() -> int:
    rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["results"]
    n = len(rows)
    print(f"总样本 N = {n}\n")

    status = collections.Counter(r["status"] for r in rows)
    print("== 状态分布 ==")
    for key, count in status.most_common():
        print(f"  {key:<28} {count:>3}  {count / n:6.1%}")

    print("\n== failure_code 分布 ==")
    for key, count in collections.Counter(
        r.get("failure_code") or "-" for r in rows
    ).most_common():
        print(f"  {key:<28} {count:>3}  {count / n:6.1%}")

    for dim in ("year", "board", "report_type"):
        print(f"\n== 按 {dim} 分层 ==")
        groups: dict[object, list[dict]] = collections.defaultdict(list)
        for r in rows:
            groups[r[dim]].append(r)
        header = f"  {'层':<10} {'N':>3} {'CONF':>5} {'SINGLE':>7} {'CONFLICT':>9}"
        print(f"{header} {'MAGN':>5} {'FAIL':>5} {'ERR':>4}")
        for key in sorted(groups, key=str):
            g = groups[key]
            c = collections.Counter(r["status"] for r in g)
            print(
                f"  {str(key):<10} {len(g):>3} {c['CONFIRMED']:>5} "
                f"{c['SINGLE_SOURCE_UNCONFIRMED']:>7} {c['SOURCE_CONFLICT']:>9} "
                f"{c['MAGNITUDE_IMPLAUSIBLE']:>5} {c['EXTRACTION_FAILED']:>5} "
                f"{c['PIPELINE_ERROR']:>4}"
            )

    print("\n== 单位来源分布（bug ② 相关） ==")
    unit_rows = [(s["unit"], s["unit_source"]) for r in rows for s in r.get("sources", [])]
    for key, count in collections.Counter(unit_rows).most_common():
        print(f"  unit={key[0]:<5} source={key[1]:<9} {count:>3}")

    print("\n== CONFIRMED 明细 ==")
    for r in rows:
        if r["status"] == "CONFIRMED":
            print(f"  {r['sec_code']} {r['report_period']} {r['board']:<8} {r['value']}")

    print("\n== SOURCE_CONFLICT 明细 ==")
    for r in rows:
        if r["status"] == "SOURCE_CONFLICT":
            vals = " | ".join(
                f"{s['source']}={s['value']}(raw={s['raw_value']},unit={s['unit']}/{s['unit_source']},col={s['column_header']},line={s['line_index']})"
                for s in r["sources"]
            )
            print(f"  {r['sec_code']} {r['report_period']} {r['board']}")
            print(f"      {vals}")
            for note in r.get("notes", []):
                print(f"      note: {note}")

    print("\n== MAGNITUDE_IMPLAUSIBLE 明细 ==")
    for r in rows:
        if r["status"] == "MAGNITUDE_IMPLAUSIBLE":
            print(f"  {r['sec_code']} {r['report_period']} {r['board']} notes={r.get('notes')}")

    print("\n== PIPELINE_ERROR 明细 ==")
    for r in rows:
        if r["status"] == "PIPELINE_ERROR":
            err = r.get("download_error") or r.get("pdftotext_error")
            print(f"  {r['sec_code']} {r['report_period']} {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
