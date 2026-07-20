"""F003 G-A — PDF → text → 巨潮 anchor 值（B108 交叉验证器，truth anchor 侧）。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from scripts.research.ashare_ep.crosscheck import cross_check

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
PDF_DIR = OUT / "pdf"
TXT_DIR = OUT / "txt"
TXT_DIR.mkdir(parents=True, exist_ok=True)

PERIOD_END = {"Q1": "0331", "H1": "0630", "Q3": "0930", "FY": "1231"}

manifest = json.loads((OUT / "manifest.json").read_text())
records = []

for item in manifest["items"]:
    aid = item["announcement_id"]
    pdf = PDF_DIR / f"{aid}.pdf"
    txt = TXT_DIR / f"{aid}.txt"
    if not txt.exists():
        subprocess.run(  # noqa: S603
            ["/opt/homebrew/bin/pdftotext", "-layout", str(pdf), str(txt)],
            check=False,
            capture_output=True,
        )
    text = txt.read_text(encoding="utf-8", errors="replace") if txt.exists() else ""
    result = cross_check(text)
    records.append(
        {
            "announcement_id": aid,
            "sec_code": item["sec_code"],
            "year": item["year"],
            "report_type": item["report_type"],
            "end_date": f"{item['year']}{PERIOD_END[item['report_type']]}",
            "title": item["title"],
            "url": item["url"],
            "anchor_status": str(result.status),
            "anchor_value": str(result.value) if result.value is not None else None,
            "failure_code": str(result.failure_code) if result.failure_code else None,
            "notes": list(result.notes),
        }
    )

(OUT / "anchors.json").write_text(
    json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
)

from collections import Counter  # noqa: E402

print("n =", len(records))
print("anchor_status:", Counter(r["anchor_status"] for r in records).most_common())
print("CONFIRMED by report_type:", Counter(
    r["report_type"] for r in records if r["anchor_status"] == "Status.CONFIRMED"
).most_common())
print("all by report_type:", Counter(r["report_type"] for r in records).most_common())
