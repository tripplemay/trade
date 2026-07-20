"""F003 G-A/G-B — 拉取被审计方（Tushare）数据并做 as-of 解析。

formation_date = **该公告自身的披露日**（从巨潮 URL 路径取），因此
resolve_as_of 应当返回「这份 PDF 当时披露的那一版」——既是对拍口径，
也顺带是一次真实的 as-of 检验。

H6：token 只经 vintage_probe.load_token() 从 .env.local 读，不落盘、不打印。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import tushare as ts

from scripts.research.ashare_pit.fetch import fetch_paged
from scripts.research.ashare_pit.vintage_probe import FIELDS, load_token

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
anchors = json.loads((OUT / "anchors.json").read_text())

DATE_IN_URL = re.compile(r"/finalpage/(\d{4})-(\d{2})-(\d{2})/")

periods = sorted({r["end_date"] for r in anchors})
print(f"periods to fetch: {len(periods)} -> {periods}")

pro = ts.pro_api(load_token())

raw: dict[str, list[dict]] = {}
reports: dict[str, dict] = {}
for period in periods:
    df, report = fetch_paged(pro.income_vip, endpoint="income_vip", period=period, fields=FIELDS)
    reports[period] = report.as_dict()
    if df.empty or report.failures:
        print(f"  {period}: FAILED pages={report.pages} rows={report.rows} {report.failures}")
        raw[period] = []
        continue
    # report_type=1 = 合并报表（与 vintage_probe 同口径）
    sub = df[df["report_type"] == "1"]
    raw[period] = sub.to_dict("records")
    print(f"  {period}: pages={report.pages} rows={report.rows} consolidated={len(sub)}")
    time.sleep(0.6)

# 只留下 holdout 涉及的证券，控制产物体积
wanted: dict[str, set[str]] = {}
for r in anchors:
    match = DATE_IN_URL.search(r["url"])
    r["formation_date"] = "".join(match.groups()) if match else None
    wanted.setdefault(r["end_date"], set())

from scripts.research.ashare_pit.audit import to_ts_code  # noqa: E402

for r in anchors:
    code = to_ts_code(r["sec_code"])
    r["ts_code"] = code
    if code:
        wanted[r["end_date"]].add(code)

slim = {
    period: [row for row in rows if row.get("ts_code") in wanted.get(period, set())]
    for period, rows in raw.items()
}
(OUT / "tushare-rows.json").write_text(
    json.dumps(slim, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
(OUT / "fetch-reports.json").write_text(
    json.dumps(reports, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
)
(OUT / "anchors.json").write_text(
    json.dumps(anchors, ensure_ascii=False, indent=2), encoding="utf-8"
)
print("total slim rows:", sum(len(v) for v in slim.values()))
print("multi-page periods:", sum(1 for r in reports.values() if r["pages"] > 1), "/", len(reports))
