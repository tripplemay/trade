"""F003 G-A — 下载 holdout PDF + build_pdf_freeze（★F002 标注为未验证的路径，本次实际执行）。"""

from __future__ import annotations

import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from scripts.research.ashare_ep.manifest import build_pdf_freeze

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
PDF_DIR = OUT / "pdf"
TXT_DIR = OUT / "txt"
PDF_DIR.mkdir(parents=True, exist_ok=True)
TXT_DIR.mkdir(parents=True, exist_ok=True)

manifest = json.loads((OUT / "manifest.json").read_text())
items = manifest["items"]

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36"


def fetch(item: dict) -> tuple[str, str]:
    aid = item["announcement_id"]
    dest = PDF_DIR / f"{aid}.pdf"
    if dest.exists() and dest.stat().st_size > 0:
        return aid, "cached"
    req = urllib.request.Request(item["url"], headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
                payload = resp.read()
            if not payload.startswith(b"%PDF"):
                return aid, f"NOT_PDF({payload[:16]!r})"
            dest.write_bytes(payload)
            return aid, "ok"
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                return aid, f"FAIL({type(exc).__name__}:{exc})"
            time.sleep(2 * (attempt + 1))
    return aid, "FAIL"


with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(fetch, items))

ok = sum(1 for _, status in results if status in ("ok", "cached"))
print(f"downloaded_ok={ok}/{len(items)}")
for aid, status in results:
    if status not in ("ok", "cached"):
        print(f"  {aid}: {status}")

# ★E11 冻结：证明评测用的是哪些字节
freeze = build_pdf_freeze({"items": items}, PDF_DIR)
(OUT / "pdf-freeze.json").write_text(
    json.dumps(freeze, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"freeze: pdf_count={freeze['pdf_count']} missing={freeze['missing_count']}")
print(f"manifest_sha256={freeze['manifest_sha256']}")
