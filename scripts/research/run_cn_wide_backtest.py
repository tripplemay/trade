#!/usr/bin/env python
"""B068 F003 — run the 4-config wide-universe backtest + write the report.

Points the unified loaders at a **research data root** (the F001 wide universe +
F003 wide prices / fundamentals / CSI 300, fetched by ``fetch_cn_wide_data.py``)
and runs :func:`run_cn_attack_wide_comparison` — the 4-config grid (2 factor × 2
weighting, exit fixed momentum_decay) with walk-forward IS/OOS, CSI 300 benchmark,
§29 over-fitting red flags, and the Q1/Q2/Q3 answers. Writes the bilingual
markdown report + the JSON payload.

Pure ``trade`` (no akshare): the backtest only reads CSVs, so this runs anywhere
the research CSVs are present (locally after copying them off the VM, or on the
VM). The production data root (B067's live seed-43 surface) is never touched —
this reads only the research root passed in ``--data-root``.

Usage::

    python scripts/research/run_cn_wide_backtest.py \
        --data-root data/research/b068 \
        --out-md docs/test-reports/B068-wide-comparison.md \
        --out-json data/research/b068/f003_wide_comparison.json
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B068 F003 wide backtest + report")
    parser.add_argument("--data-root", type=Path, required=True, help="research data root")
    parser.add_argument("--out-md", type=Path, required=True, help="markdown report path")
    parser.add_argument("--out-json", type=Path, required=True, help="JSON payload path")
    parser.add_argument("--start", type=_parse_date, default=None)
    parser.add_argument("--end", type=_parse_date, default=None)
    parser.add_argument("--run-id", type=str, default="b068-f003-wide")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Redirect the unified loaders to the research root BEFORE importing them, so
    # the wide research data is read and the production root is untouched.
    os.environ["WORKBENCH_DATA_ROOT"] = str(args.data_root.resolve())

    from trade.reporting.cn_attack_wide_comparison import (
        build_cn_attack_wide_payload,
        render_cn_attack_wide_markdown,
        run_cn_attack_wide_comparison,
    )

    comparison = run_cn_attack_wide_comparison(args.start, args.end)
    markdown = render_cn_attack_wide_markdown(comparison)
    payload = build_cn_attack_wide_payload(comparison, args.run_id)

    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(markdown, encoding="utf-8")
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(markdown)
    print("\n--- payload written to", args.out_json, "---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
