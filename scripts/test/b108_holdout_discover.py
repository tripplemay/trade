"""B108 F003 — Evaluator 侧候选池发现脚本（不属于 F001/F002 交付物）。

存在理由：F002 的 ``sample_cli.discover_candidates`` 联网路径在
``with CninfoClient() as client:`` 处崩溃（CninfoClient 未实现上下文管理器协议），
而该路径恰好是 H3 禁止 Generator 运行、因而从未被执行过的那一条。

本脚本只做「把巨潮候选池抓下来存成 candidates.json」，抽样逻辑仍然交给 F002 的
``sample_cli --candidates-json``，以便真正被验收的抽样代码保持在测试之中。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scripts.research.ashare_ep.sample_cli import _QUERY_SPECS
from scripts.test.ashare_as_filed_data_pilot import (
    CninfoClient,
    clean_title,
    is_regular_report_title,
)

MAX_PAGES = 12


def discover(years: tuple[int, ...], report_types: tuple[str, ...]) -> dict[str, Any]:
    client = CninfoClient()
    candidates: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    seen: set[str] = set()

    for year in years:
        for report_type in report_types:
            spec = _QUERY_SPECS[report_type]
            query_year = year + int(spec["year_offset"])
            start = f"{query_year}-{spec['start']}"
            end = f"{query_year}-{spec['end']}"
            rows_seen = 0
            found = 0
            for page in range(1, MAX_PAGES + 1):
                payload = client.query(
                    page=page, start=start, end=end, category=str(spec["category"])
                )
                rows = list(payload.get("announcements") or [])
                rows_seen += len(rows)
                for row in rows:
                    announcement_id = str(row.get("announcementId") or "")
                    adjunct = str(row.get("adjunctUrl") or "")
                    title = clean_title(row.get("announcementTitle"))
                    if not announcement_id or not adjunct or announcement_id in seen:
                        continue
                    if not is_regular_report_title(title, year, str(spec["pattern"])):
                        continue
                    seen.add(announcement_id)
                    candidates.append(
                        {
                            "announcement_id": announcement_id,
                            "sec_code": str(row.get("secCode") or ""),
                            "title": title,
                            "year": year,
                            "report_type": report_type,
                            "url": f"https://static.cninfo.com.cn/{adjunct}",
                        }
                    )
                    found += 1
                if not payload.get("hasMore"):
                    break
            diagnostics.append(
                {
                    "year": year,
                    "report_type": report_type,
                    "query_start": start,
                    "query_end": end,
                    "rows_seen": rows_seen,
                    "eligible": found,
                }
            )
            print(
                f"{year} {report_type}: rows={rows_seen} eligible={found}",
                file=sys.stderr,
                flush=True,
            )

    return {"candidates": candidates, "diagnostics": diagnostics}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    years = tuple(int(x) for x in argv[0].split(","))
    report_types = tuple(argv[1].split(","))
    out = Path(argv[2])
    payload = discover(years, report_types)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"candidates: {len(payload['candidates'])} -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
