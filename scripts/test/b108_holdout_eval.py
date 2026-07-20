"""B108 F003 — Evaluator 侧 holdout 评测 harness。

流程：冻结的 manifest → 下载 PDF → ``pdftotext -layout`` → ``crosscheck.cross_check``。
只调用 F001 的公开入口，不改动被验收代码。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import requests

from scripts.research.ashare_ep.crosscheck import cross_check

ROOT = Path("data/research/b108")
PDF_DIR = ROOT / "pdf"
TXT_DIR = ROOT / "txt"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.cninfo.com.cn/",
}


def fetch(item: dict[str, Any]) -> dict[str, Any]:
    aid = item["announcement_id"]
    pdf_path = PDF_DIR / f"{aid}.pdf"
    txt_path = TXT_DIR / f"{aid}.txt"
    out: dict[str, Any] = {"announcement_id": aid}

    if not pdf_path.exists() or pdf_path.stat().st_size < 5000:
        last: str | None = None
        for attempt in range(4):
            try:
                resp = requests.get(item["url"], headers=HEADERS, timeout=(10, 120))
                resp.raise_for_status()
                if len(resp.content) < 5000:
                    raise ValueError(f"suspiciously small body: {len(resp.content)}")
                pdf_path.write_bytes(resp.content)
                break
            except Exception as exc:  # noqa: BLE001 - bounded public-source retry
                last = f"{type(exc).__name__}: {exc}"
                time.sleep(1.0 * (attempt + 1))
        else:
            out["download_error"] = last
            return out

    out["pdf_bytes"] = pdf_path.stat().st_size

    if not txt_path.exists():
        proc = subprocess.run(  # noqa: S603
            ["/opt/homebrew/bin/pdftotext", "-layout", str(pdf_path), str(txt_path)],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if proc.returncode != 0:
            out["pdftotext_error"] = proc.stderr[:500]
            return out
    out["txt_chars"] = txt_path.stat().st_size
    return out


def evaluate(item: dict[str, Any]) -> dict[str, Any]:
    row = dict(item)
    row.update(fetch(item))
    if "download_error" in row or "pdftotext_error" in row:
        row["status"] = "PIPELINE_ERROR"
        return row

    txt_path = TXT_DIR / f"{item['announcement_id']}.txt"
    text = txt_path.read_text(encoding="utf-8", errors="replace")
    result = cross_check(text)
    row["status"] = result.status.name if hasattr(result.status, "name") else str(result.status)
    row["value"] = str(result.value) if result.value is not None else None
    row["failure_code"] = (
        result.failure_code.name if result.failure_code is not None else None
    )
    row["sources"] = [
        {
            "source": s.source,
            "value": str(s.value),
            "raw_value": str(s.raw_value),
            "unit": s.unit,
            "unit_source": s.unit_source,
            "label": s.label,
            "column_header": s.column_header,
            "line_index": s.line_index,
        }
        for s in result.sources
    ]
    row["notes"] = list(result.notes)
    return row


def main() -> int:
    manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    out_path = Path(sys.argv[2])
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    TXT_DIR.mkdir(parents=True, exist_ok=True)

    items = manifest["items"]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, row in enumerate(pool.map(evaluate, items), 1):
            results.append(row)
            print(
                f"[{i}/{len(items)}] {row['sec_code']} {row['report_period']} "
                f"{row['board']} -> {row['status']} {row.get('value')}",
                file=sys.stderr,
                flush=True,
            )

    results.sort(key=lambda r: (r["year"], r["board"], r["report_type"], r["sec_code"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"wrote {out_path} ({len(results)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
