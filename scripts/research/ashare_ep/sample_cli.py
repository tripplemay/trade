"""B108 F002 — 分层抽样 CLI。**只产 manifest，不下载 PDF、不抽取数值、不做评测。**

★H3 边界：本工具由 Generator 交付，但**抽样动作属于 F003 的 Codex**。Generator 只以
``--candidates-json`` 离线模式验证工具本身，不得对巨潮发起真实检索——一旦抽了样本，
样本就进了 Generator 的上下文，holdout 当场失效。

用法::

    # Codex 抽 holdout（自选 seed，排除已烧掉的 50 份）
    python -m scripts.research.ashare_ep.sample_cli \\
        --seed 20260720 --years 2015,2019,2023,2025 --quota 4 \\
        --exclude-manifest docs/test-reports/ashare-as-filed-data-pilot-2026-07-12.json \\
        --out data/research/b108/holdout-manifest.json

    # 离线验证确定性（不联网）
    python -m scripts.research.ashare_ep.sample_cli \\
        --seed 1 --candidates-json fixture.json --out /tmp/m.json
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.research.ashare_ep.manifest import (
    build_manifest,
    build_provenance,
    load_excluded_ids,
    write_manifest,
    write_provenance,
)
from scripts.research.ashare_ep.sampling import (
    REPORT_TYPES,
    Candidate,
    coverage_report,
    expected_strata,
    select_stratified,
)

# 巨潮检索规格。``year_offset`` 是年报特有的：Y 年的年度报告在 Y+1 年 1-4 月披露，
# 所以查询窗口要往后挪一年，而标题里的年份仍是 Y。
_QUERY_SPECS: dict[str, dict[str, Any]] = {
    "Q1": {
        "category": "category_yjdbg_szsh;",
        "start": "04-01",
        "end": "05-10",
        "pattern": r"年(?:第)?一季度报告",
        "year_offset": 0,
    },
    "H1": {
        "category": "category_bndbg_szsh;",
        "start": "07-01",
        "end": "09-30",
        "pattern": r"年半年度报告",
        "year_offset": 0,
    },
    "Q3": {
        "category": "category_sjdbg_szsh;",
        "start": "10-01",
        "end": "11-15",
        "pattern": r"年(?:第)?三季度报告",
        "year_offset": 0,
    },
    "FY": {
        "category": "category_ndbg_szsh;",
        "start": "01-01",
        "end": "04-30",
        "pattern": r"年年度报告",
        "year_offset": 1,
    },
}

_MAX_QUERY_PAGES = 8


def discover_candidates(
    years: tuple[int, ...],
    report_types: tuple[str, ...],
    *,
    max_pages: int = _MAX_QUERY_PAGES,
) -> tuple[list[Candidate], list[dict[str, Any]]]:
    """联网检索候选池。★Generator 不得调用本函数（H3）。"""
    # 延迟导入：离线路径不应因为网络依赖而无法运行
    from scripts.test.ashare_as_filed_data_pilot import (  # noqa: PLC0415
        CninfoClient,
        clean_title,
        is_regular_report_title,
    )

    candidates: list[Candidate] = []
    diagnostics: list[dict[str, Any]] = []
    seen: set[str] = set()

    # ★E01 修复：CninfoClient 没有实现上下文管理器协议，原来的 `with CninfoClient()`
    # 第一行就抛 TypeError。这条是 F003 唯一必走的路径，交付时却从未被执行过——
    # 因为 H3 禁止 Generator 跑联网路径，而离线路径绕开了它。
    # 教训：被规则挡住不等于被验证过；无法执行的路径必须显式标注为未验证。
    client = CninfoClient()
    try:
        for year in years:
            for report_type in report_types:
                spec = _QUERY_SPECS[report_type]
                query_year = year + int(spec["year_offset"])
                start = f"{query_year}-{spec['start']}"
                end = f"{query_year}-{spec['end']}"
                rows_seen = 0
                found = 0
                pages_used = 0
                exhausted = False

                for page in range(1, max_pages + 1):
                    pages_used = page
                    payload = client.query(
                        page=page, start=start, end=end, category=str(spec["category"])
                    )
                    rows = list(payload.get("announcements") or [])
                    rows_seen += len(rows)
                    for row in rows:
                        code = str(row.get("secCode") or "")
                        title = clean_title(row.get("announcementTitle"))
                        announcement_id = str(row.get("announcementId") or "")
                        adjunct = str(row.get("adjunctUrl") or "")
                        if not announcement_id or not adjunct or announcement_id in seen:
                            continue
                        if not is_regular_report_title(title, year, str(spec["pattern"])):
                            continue
                        seen.add(announcement_id)
                        candidates.append(
                            Candidate(
                                announcement_id=announcement_id,
                                sec_code=code,
                                title=title,
                                year=year,
                                report_type=report_type,
                                url=f"https://static.cninfo.com.cn/{adjunct}",
                            )
                        )
                        found += 1
                    if not payload.get("hasMore"):
                        exhausted = True
                        break

                diagnostics.append(
                    {
                        "year": year,
                        "report_type": report_type,
                        "query_start": start,
                        "query_end": end,
                        "rows_seen": rows_seen,
                        "eligible": found,
                        "pages_used": pages_used,
                        # ★no-silent-caps：撞到翻页上限意味着候选池被截断，
                        # 该层的抽样不是从完整总体里抽的，必须显式披露。
                        "pagination_exhausted": exhausted,
                        "hit_page_cap": not exhausted and pages_used >= max_pages,
                    }
                )
    finally:
        client.session.close()

    return candidates, diagnostics


def load_candidates_json(path: Path) -> list[Candidate]:
    """离线候选池，用于在不联网的情况下验证抽样逻辑。"""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [
        Candidate(
            announcement_id=str(item["announcement_id"]),
            sec_code=str(item["sec_code"]),
            title=str(item.get("title", "")),
            year=int(item["year"]),
            report_type=str(item["report_type"]),
            url=str(item.get("url", "")),
        )
        for item in payload["candidates"]
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sample_cli",
        description="B108 确定性分层抽样——只产 manifest，不下载不抽取不评测",
    )
    parser.add_argument(
        "--seed", type=int, required=True, help="主随机种子；同 seed 同候选池必然复现"
    )
    parser.add_argument("--years", type=str, default="", help="逗号分隔年份，如 2015,2019,2023")
    parser.add_argument(
        "--report-types",
        type=str,
        default=",".join(REPORT_TYPES),
        help=f"逗号分隔报告类型，默认 {','.join(REPORT_TYPES)}",
    )
    parser.add_argument("--quota", type=int, default=4, help="每层配额")
    parser.add_argument("--out", type=Path, required=True, help="manifest 输出路径")
    parser.add_argument("--provenance-out", type=Path, default=None, help="溯源信息输出路径")
    parser.add_argument(
        "--exclude-manifest",
        type=Path,
        default=None,
        help="排除该 manifest / pilot 报告中出现过的公告 ID",
    )
    parser.add_argument(
        "--candidates-json",
        type=Path,
        default=None,
        help="离线候选池；给定时不联网（Generator 只用这条路径）",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    report_types = tuple(item.strip() for item in args.report_types.split(",") if item.strip())
    unknown = set(report_types) - set(_QUERY_SPECS)
    if unknown:
        print(f"未知报告类型：{sorted(unknown)}", file=sys.stderr)
        return 2

    excluded = (
        load_excluded_ids(args.exclude_manifest) if args.exclude_manifest else frozenset()
    )

    if args.candidates_json:
        candidates = load_candidates_json(args.candidates_json)
        diagnostics: list[dict[str, Any]] = [
            {"source": "offline", "path": str(args.candidates_json)}
        ]
        years = tuple(sorted({item.year for item in candidates}))
    else:
        years = tuple(int(item) for item in args.years.split(",") if item.strip())
        if not years:
            print("联网模式必须给 --years", file=sys.stderr)
            return 2
        candidates, diagnostics = discover_candidates(years, report_types)

    selected = select_stratified(
        candidates,
        quota_per_stratum=args.quota,
        seed=args.seed,
        exclude_ids=excluded,
    )

    manifest = build_manifest(
        selected,
        seed=args.seed,
        quota_per_stratum=args.quota,
        years=years,
        report_types=report_types,
        excluded_manifest=str(args.exclude_manifest) if args.exclude_manifest else None,
    )
    digest = write_manifest(manifest, args.out)

    coverage = coverage_report(
        candidates,
        selected,
        quota_per_stratum=args.quota,
        # 传入应有的层，让候选数为 0 的整层也出现在报告里（E08）
        expected=expected_strata(years, report_types),
    )
    if args.provenance_out:
        write_provenance(
            build_provenance(
                manifest_hash=digest,
                generated_at=datetime.now(UTC).isoformat(),
                query_diagnostics=diagnostics,
                coverage=coverage,
                candidate_pool_size=len(candidates),
            ),
            args.provenance_out,
        )

    short = [row for row in coverage if not row["quota_met"]]
    print(f"manifest: {args.out}")
    print(f"sha256:   {digest}")
    print(f"selected: {len(selected)} / 候选池 {len(candidates)} / 排除 {len(excluded)}")
    if short:
        # 配额没满必须刺眼地说出来，不能让下游把「抽不满」读成「没问题」
        print(f"★ 有 {len(short)} 个层未达配额：", file=sys.stderr)
        for row in short:
            print(
                f"    {row['year']} {row['board']} {row['report_type']}: "
                f"{row['selected']}/{row['quota']}（候选 {row['available']}）",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
