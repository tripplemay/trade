"""F003 — 独立复核 B109 的跨批次头条发现：Tushare 单次调用静默截断。

方法：对同一期同时做 (a) 无 limit/offset 的单次调用 (b) fetch_paged 分页，比较行数。
选 20211231（分页实测 10740 行 > 观测上限 9000）。
"""

from __future__ import annotations

import tushare as ts

from scripts.research.ashare_pit.fetch import fetch_paged, looks_truncated
from scripts.research.ashare_pit.vintage_probe import FIELDS, load_token

pro = ts.pro_api(load_token())
PERIOD = "20211231"

single = pro.income_vip(period=PERIOD, fields=FIELDS)
print(f"单次调用 rows = {len(single)}   looks_truncated={looks_truncated(len(single))}")

paged, report = fetch_paged(pro.income_vip, endpoint="income_vip", period=PERIOD, fields=FIELDS)
print(f"分页    rows = {len(paged)}   pages={report.pages}  failures={report.failures}")

missing = len(paged) - len(single)
print(f"漏掉 {missing} 行 ({missing / len(paged):.2%})")

# 截断是否均匀？按 update_flag 比较构成
for flag in ("0", "1"):
    s = (single["update_flag"] == flag).sum()
    p = (paged["update_flag"] == flag).sum()
    print(f"  update_flag={flag}: 单次 {s} / 分页 {p} → 漏 {(p - s) / p:.1%}" if p else "")
