"""F003 G-A — 独立抽样（评测方自选 seed，H3）。

seed 由本次验收 agent 选定，仓库内无预置 manifest / 无默认 seed（已核）。
排除 B108 两轮已烧语料（样本内 26.3% vs 样本外 16.7%，见 project-status.md）。
"""

from __future__ import annotations

import json
from pathlib import Path

from scripts.research.ashare_ep.sampling import Candidate, coverage_report, expected_strata
from scripts.research.ashare_pit.audit import select_audit_sample

REPO = Path("/Users/yixingzhou/project/trade")
OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
OUT.mkdir(parents=True, exist_ok=True)

# ★F003 验收方自选。仓库内不存在此值。
SEED = 570193
QUOTA = 2

pool_raw = json.loads((REPO / "data/research/b108/candidates.json").read_text())["candidates"]
candidates = [
    Candidate(
        announcement_id=str(item["announcement_id"]),
        sec_code=str(item["sec_code"]),
        title=str(item["title"]),
        year=int(item["year"]),
        report_type=str(item["report_type"]),
        url=str(item["url"]),
    )
    for item in pool_raw
]

# 已烧语料：两轮 holdout manifest + 本地实际下载过的 PDF 文件名
burned: set[str] = set()
for rel in (
    "docs/test-reports/B108-holdout/holdout-manifest.json",
    "docs/test-reports/B108-holdout-r2/holdout-manifest.json",
    "docs/test-reports/B108-holdout-r2/exclude-merged.json",
):
    path = REPO / rel
    if path.exists():
        payload = json.loads(path.read_text())
        for key in ("items", "documents"):
            for item in payload.get(key, []) or []:
                if aid := item.get("announcement_id"):
                    burned.add(str(aid))
for pdf_dir in ("data/research/b108/pdf", "data/research/b108r2/pdf"):
    for path in (REPO / pdf_dir).glob("*.pdf"):
        burned.add(path.stem)

selected = select_audit_sample(
    candidates, seed=SEED, quota_per_stratum=QUOTA, exclude_ids=frozenset(burned)
)

years = tuple(sorted({item.year for item in candidates}))
coverage = coverage_report(
    candidates, selected, quota_per_stratum=QUOTA, expected=expected_strata(years)
)

print(f"pool={len(candidates)} burned_excluded={len(burned)} selected={len(selected)}")
print(f"overlap_with_burned={len({i.announcement_id for i in selected} & burned)}")
unmet = [row for row in coverage if not row["quota_met"]]
print(f"strata_total={len(coverage)} quota_unmet={len(unmet)}")
for row in unmet:
    print("  UNMET", row)

(OUT / "manifest.json").write_text(
    json.dumps(
        {
            "seed": SEED,
            "quota_per_stratum": QUOTA,
            "n_selected": len(selected),
            "n_excluded_burned": len(burned),
            "items": [
                {
                    "announcement_id": i.announcement_id,
                    "sec_code": i.sec_code,
                    "year": i.year,
                    "report_type": i.report_type,
                    "title": i.title,
                    "url": i.url,
                }
                for i in selected
            ],
            "coverage": coverage,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
print(f"wrote {OUT / 'manifest.json'}")
