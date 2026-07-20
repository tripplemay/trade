"""B109 F002 — 月末 PIT 面板装配 CLI（联网）。

把 F002 的四块接起来跑出真实覆盖漏斗::

    .venv/bin/python -m scripts.research.ashare_pit.panel_cli \\
        --start 202303 --end 202312 --out docs/audits/B109-F002-panel.json

产出**只是覆盖诊断**，不计算 E/P、不产生任何收益数字（H5）。
凭据只从 ``.env.local`` 读（H6），token 不出现在输出、日志或任何产物里。

★成本提示：每个形成日 1 次 `daily_basic`，每个报告期 1 次 `income_vip`，
另加 2 次宇宙调用。跑长区间前先估算调用数——本仓的 Tushare 额度是付费的。
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from scripts.research.ashare_pit.fetch import (
    FetchReport,
    fetch_paged,
    fetch_single_checked,
)
from scripts.research.ashare_pit.marketcap import build_point, summarize
from scripts.research.ashare_pit.pipeline import (
    PanelRow,
    build_funnel,
    flag0_retention,
    last_trade_date_on_or_before,
    mandatory_disclosures,
    month_end_dates,
    select_latest_resolved,
    summarize_panel,
    to_jsonable,
)
from scripts.research.ashare_pit.resolver import build_versions, resolve_as_of
from scripts.research.ashare_pit.universe import (
    ALL_LIST_STATUS,
    build_securities,
    summarize_universe,
    universe_as_of,
)
from scripts.research.ashare_pit.vintage_probe import load_token

INCOME_FIELDS = "ts_code,ann_date,f_ann_date,end_date,report_type,update_flag,n_income_attr_p"
BASIC_FIELDS = "ts_code,trade_date,close,total_share,total_mv"
STOCK_FIELDS = "ts_code,symbol,name,list_status,list_date,delist_date"

CONSOLIDATED_REPORT_TYPE = "1"
_THROTTLE_SECONDS = 0.6
_MAX_ATTEMPTS = 3


def _call(fn: Any, **kwargs: Any) -> Any | None:
    """有界重试。最终失败返回 ``None`` 由调用方显式记录——不静默跳过（H4）。

    ★只用于**确信不分页**的小结果集（`trade_cal` 单月）。批量接口一律走
    :func:`~scripts.research.ashare_pit.fetch.fetch_paged`——见该模块 docstring 的
    静默截断实测（`income_vip` 单次漏 10.8%，且 `flag=0` 行漏 18.7%）。
    """
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return fn(**kwargs)
        except Exception:  # noqa: BLE001 - 有界重试后以 None 显式暴露
            if attempt + 1 < _MAX_ATTEMPTS:
                time.sleep(3.0 * (attempt + 1))
    return None


def quarters_before(formation_date: str, count: int) -> list[str]:
    """形成日之前的 ``count`` 个报告期（``YYYYMMDD``），由近及远。"""
    year, month = int(formation_date[:4]), int(formation_date[4:6])
    quarter_end = ((month - 1) // 3) * 3
    if quarter_end == 0:
        year, quarter_end = year - 1, 12
    periods: list[str] = []
    for _ in range(count):
        day = 31 if quarter_end in (3, 12) else 30
        periods.append(f"{year:04d}{quarter_end:02d}{day:02d}")
        quarter_end -= 3
        if quarter_end == 0:
            year, quarter_end = year - 1, 12
    return periods


def fetch_universe(pro: Any) -> tuple[list[dict[str, Any]], list[FetchReport]]:
    """拉全状态证券主数据。★L/D/P 三态都要（禁令 #11：只拉 L = 幸存者偏差）。

    实测 L=5528 / D=338 / P=0，均远低于单次上限，故走 checked 单次；
    触顶时 ``truncation_suspected`` 会置位，由调用方暴露。
    """
    rows: list[dict[str, Any]] = []
    reports: list[FetchReport] = []
    for status in ALL_LIST_STATUS:
        df, report = fetch_single_checked(
            pro.stock_basic,
            endpoint=f"stock_basic:{status}",
            list_status=status,
            fields=STOCK_FIELDS,
        )
        reports.append(report)
        rows.extend(df.to_dict("records"))
        time.sleep(_THROTTLE_SECONDS)
    return rows, reports


def fetch_period(pro: Any, period: str) -> tuple[list[dict[str, Any]] | None, FetchReport]:
    """拉一期合并利润表。★必须分页——单次调用在 2019/2021/2022 年报期恰好返回
    9000 行（实测漏 10.8%，其中 ``flag=0`` 行漏 18.7%）。
    """
    df, report = fetch_paged(
        pro.income_vip,
        endpoint="income_vip",
        period=period,
        fields=INCOME_FIELDS,
    )
    if report.failures or df.empty:
        return None, report
    filtered = df[df["report_type"] == CONSOLIDATED_REPORT_TYPE]
    return filtered.to_dict("records"), report


def run(start: str, end: str, *, lookback_quarters: int) -> dict[str, Any]:
    import tushare as ts  # noqa: PLC0415 - 延迟导入，离线单测不需要网络依赖

    pro = ts.pro_api(load_token())
    failures: list[str] = []
    fetch_reports: list[FetchReport] = []

    stock_rows, universe_reports = fetch_universe(pro)
    fetch_reports.extend(universe_reports)
    securities = build_securities(stock_rows)

    formation_dates = month_end_dates(start, end)
    period_cache: dict[str, list[dict[str, Any]]] = {}
    retention: dict[str, float] = {}
    funnels: list[dict[str, Any]] = []

    for formation_date in formation_dates:
        periods = quarters_before(formation_date, lookback_quarters)
        for period in periods:
            if period in period_cache:
                continue
            rows, period_report = fetch_period(pro, period)
            fetch_reports.append(period_report)
            if rows is None:
                failures.append(f"income_vip:{period}")
                continue
            period_cache[period] = rows
            retention[period] = flag0_retention(rows)
            time.sleep(_THROTTLE_SECONDS)

        # 分母：落到不晚于形成日的最后一个交易日（不向后取——那是前视）
        basic, basic_report = fetch_paged(
            pro.daily_basic, endpoint="daily_basic", trade_date=formation_date, fields=BASIC_FIELDS
        )
        fetch_reports.append(basic_report)
        if basic.empty:
            calendar_df = _call(
                pro.trade_cal,
                start_date=formation_date[:6] + "01",
                end_date=formation_date,
                is_open="1",
            )
            trade_date = (
                last_trade_date_on_or_before(calendar_df["cal_date"].tolist(), formation_date)
                if calendar_df is not None and not calendar_df.empty
                else None
            )
            if trade_date is None:
                failures.append(f"trade_cal:{formation_date}")
                continue
            basic, basic_report = fetch_paged(
                pro.daily_basic, endpoint="daily_basic", trade_date=trade_date, fields=BASIC_FIELDS
            )
            fetch_reports.append(basic_report)
            if basic.empty:
                failures.append(f"daily_basic:{trade_date}")
                continue
        time.sleep(_THROTTLE_SECONDS)

        points = {}
        for row in basic.to_dict("records"):
            point = build_point(row)
            if point is not None:
                points[point.ts_code] = point

        # ★按 ts_code 建索引，每期只规范化一次。
        # 原实现对**每个证券**都重扫全部行 → O(证券 × 期次 × 行数) ≈ 2×10⁸ 次，
        # 两个月的面板跑 10 分钟都出不来。
        versions_by_period: dict[str, dict[str, list[Any]]] = {}
        for period in periods:
            index: dict[str, list[Any]] = {}
            for version in build_versions(period_cache.get(period, [])):
                index.setdefault(version.ts_code, []).append(version)
            versions_by_period[period] = index

        in_universe = universe_as_of(securities, formation_date)
        rows_out: list[PanelRow] = []
        for security in in_universe:
            resolved_by_period = {}
            for period in periods:
                versions = versions_by_period[period].get(security.ts_code, [])
                resolved_by_period[period] = resolve_as_of(versions, formation_date)
            end_date, fact = select_latest_resolved(resolved_by_period)
            if fact is None:
                fact = resolve_as_of([], formation_date)
                end_date = ""
            rows_out.append(
                PanelRow(
                    ts_code=security.ts_code,
                    formation_date=formation_date,
                    end_date=end_date or "",
                    fact=fact,
                    market_cap=points.get(security.ts_code),
                )
            )

        funnel = build_funnel(rows_out, universe_size=len(in_universe))
        funnel["universe"] = summarize_universe(securities, formation_date)
        funnel["market_cap"] = summarize(points.values())
        funnels.append(funnel)

    total_ambiguous = sum(int(item["fact_version_ambiguous"]) for item in funnels)
    return {
        "params": {"start": start, "end": end, "lookback_quarters": lookback_quarters},
        "fetch_failures": failures,
        # ★分页审计：页数/行数/触顶标志全部留痕。没有这一段，
        # 「拉到的就是全量」只是一个无法复核的断言（实测它经常是错的）。
        "fetch_reports": [item.as_dict() for item in fetch_reports],
        "truncation_suspected": [
            item.endpoint for item in fetch_reports if item.truncation_suspected
        ],
        "panel": summarize_panel(funnels),
        "disclosures": mandatory_disclosures(
            fact_version_ambiguous=total_ambiguous,
            flag0_retention_by_period=retention,
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B109 F002 月末 PIT 面板覆盖漏斗")
    parser.add_argument("--start", required=True, help="起始月 YYYYMM")
    parser.add_argument("--end", required=True, help="结束月 YYYYMM")
    parser.add_argument("--lookback-quarters", type=int, default=5)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    result = run(args.start, args.end, lookback_quarters=args.lookback_quarters)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(to_jsonable(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    panel = result["panel"]
    print(f"形成日数: {panel['n_formation_dates']}")
    print(f"可用覆盖（合并）: {panel['pooled_usable_fraction']:.2%}")
    print(f"最差单月覆盖: {panel['worst_month_usable_fraction']:.2%}")
    print(f"FACT_VERSION_AMBIGUOUS 累计: {panel['total_fact_version_ambiguous']}")
    total_rows = sum(int(item["rows"]) for item in result["fetch_reports"])
    print(f"分页拉取: {len(result['fetch_reports'])} 次调用 / {total_rows} 行")
    if result["truncation_suspected"]:
        print(f"★★ 疑似触顶截断（须改走分页）: {result['truncation_suspected']}")
    if result["fetch_failures"]:
        print(f"★ 拉取失败（未计入统计）: {result['fetch_failures']}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
