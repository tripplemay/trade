"""B110 F002 — 2013-01 至 2024-12 连续 144 月末 E/P 面板（联网 CLI）。

## 与 B109 `panel_cli.py` 的三处关键差别

1. ★**全期一次性预取，不滑窗**。B109 的 ``lookback_quarters=5`` 是确定的缺陷：
   形成日 `20130131` 的最新可见期是 `20120930`（FY2012 未披露），Q3 锚点需要
   `C_Q3(2011)` = `20110930`，**不在 5 期窗口内**。滑窗会让每年 1-3 月的形成日
   系统性 null，**且只打早年**（早年迟报多、锚点更常向后滑）——这些 null 会被记成
   「数据缺失」而不是「窗口开小了」，直接放大覆盖污染项。预取 54 期后
   ``PERIOD_NOT_FETCHED`` 结构上不可能触发，可直接断言其计数 == 0。
2. ★**`stock_basic` 走 `fetch_paged`**。B109 `panel_cli.py:99` 用
   ``fetch_single_checked``，而 L=5,529 不命中任何已知 cap → 真截断会无声无息，
   而截断宇宙 = 直接重新引入禁令 #11 的幸存者偏差。**这是全项目截断后果最严重的一处。**
3. ★**`trade_cal` 一次性预取**。B109 是「先打自然月末的 `daily_basic`，空了再补日历」，
   而实测 144 个自然月末有 **49 个（34%）不是交易日** → 白扔约 100-190 次调用。

## 落盘

- 原始拉取一律缓存到 ``data/research/B110/``（git 已忽略）。**重跑零 API 成本**，
  F003 迭代与 F004 复算因此不必再花钱。
- ``docs/audits/B110-F002-monthly-funnel.csv`` —— 144 行扁平长表，供 Codex 逐列断言。
- ``docs/audits/B110-F002-panel.json`` —— 披露、抓取审计、成本留痕。
- ``data/research/B110/ep_panel.csv.gz`` —— (证券 × 形成日) 明细，F003 的输入。

★H6：token 只从 `.env.local` 读，不入日志与产物。
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import time
from collections.abc import Iterable, Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.research.ashare_pit.codes import FactVersion
from scripts.research.ashare_pit.ep_panel import (
    EpPanelRow,
    build_ep_funnel,
    csv_header,
    funnel_closes,
    funnel_to_csv_row,
)
from scripts.research.ashare_pit.fetch import DEFAULT_PAGE_SIZE, FetchReport, fetch_paged
from scripts.research.ashare_pit.marketcap import build_point
from scripts.research.ashare_pit.marketcap import summarize as summarize_marketcap
from scripts.research.ashare_pit.pipeline import (
    flag0_retention,
    last_trade_date_on_or_before,
    mandatory_disclosures,
    month_end_dates,
    summarize_panel,
    to_jsonable,
)
from scripts.research.ashare_pit.resolver import build_versions, to_decimal
from scripts.research.ashare_pit.returns import (
    DELIST_STUBS,
    PricePoint,
    forward_return,
    summarize_returns,
)
from scripts.research.ashare_pit.ttm import (
    STANDARD_QUARTER_ENDS,
    compute_ttm,
    step_without_filing,
)
from scripts.research.ashare_pit.universe import (
    ALL_LIST_STATUS,
    build_securities,
    summarize_universe,
    universe_as_of,
)
from scripts.research.ashare_pit.vintage_probe import load_token

#: 相对 B109 新增 comp_type / n_income / total_profit 三个**诊断**字段（边际成本≈0），
#: F004 人工复算 ≥50 个证券-形成日时需要。★禁 fields='*'（60+ 字段拖慢分页）。
INCOME_FIELDS = (
    "ts_code,ann_date,f_ann_date,end_date,report_type,comp_type,"
    "update_flag,n_income_attr_p,n_income,total_profit"
)
BASIC_FIELDS = "ts_code,trade_date,close,total_share,total_mv"
STOCK_FIELDS = "ts_code,symbol,name,list_status,list_date,delist_date"
CONSOLIDATED = "1"
DIRECT_QUARTER = "2"

#: 期次范围。★不是 48 期——见模块 docstring 第 1 点。
FIRST_PERIOD = "20110930"
LAST_PERIOD = "20241231"

_THROTTLE = 0.3
#: `report_type=1` 占比闸门。裸 `== "1"` 在分页 concat 后 dtype 漂成 int64 时会**整期
#: 静默归零**（返回空表不是 None，不进 failures）。实测不传 report_type 时占比 100%。
_RT1_SHARE_FLOOR = 0.30


def quarter_ends(first: str = FIRST_PERIOD, last: str = LAST_PERIOD) -> list[str]:
    """区间内全部标准报告期末，升序。"""
    out: list[str] = []
    for year in range(int(first[:4]), int(last[:4]) + 1):
        for suffix in STANDARD_QUARTER_ENDS:
            period = f"{year}{suffix}"
            if first <= period <= last:
                out.append(period)
    return out


class Ledger:
    """API 成本留痕（spec §8 硬性：不设中间确认门 ≠ 不留痕）。"""

    def __init__(self) -> None:
        self.reports: list[FetchReport] = []
        self.started = time.monotonic()

    def add(self, report: FetchReport) -> None:
        self.reports.append(report)

    @property
    def calls(self) -> int:
        return sum(item.pages for item in self.reports)

    @property
    def rows(self) -> int:
        return sum(item.rows for item in self.reports)

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started

    def as_dict(self) -> dict[str, Any]:
        return {
            "api_calls_total": self.calls,
            "api_rows_total": self.rows,
            "elapsed_seconds": round(self.elapsed, 1),
            "failures": [item for report in self.reports for item in report.failures],
            "truncation_suspected": [
                report.endpoint for report in self.reports if report.truncation_suspected
            ],
            "reports": [report.as_dict() for report in self.reports],
        }


#: ★缺失值经 ``astype(str)`` 会变成字面量 "nan"，它**不是空串**：
#: `build_versions` 的空值判断放它过去，而 "nan" 与日期做字典序比较时
#: "n" > "2" → 该行被当成「尚未披露」。必须在入口统一归一成空串。
_NULL_TOKENS = frozenset({"nan", "NaN", "None", "NaT", "<NA>", "none", "null"})


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    return frame.astype(str).replace(list(_NULL_TOKENS), "")


def _cached(cache_dir: Path, name: str) -> pd.DataFrame | None:
    """读缓存。★损坏或空的缓存一律当作未命中并就地删除。

    进程被中断时 `_store` 可能留下半截文件；把它读成「这一期没有数据」是
    本模块最不该犯的错误（见 `_LONG_BACKOFF_SECONDS` 上方对静默空表的说明）。
    """
    path = cache_dir / f"{name}.csv.gz"
    if not path.exists():
        return None
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except (pd.errors.EmptyDataError, OSError, EOFError):
        path.unlink(missing_ok=True)
        return None
    if frame.empty:
        path.unlink(missing_ok=True)
        return None
    return _normalize(frame)


def _store(cache_dir: Path, name: str, frame: pd.DataFrame) -> None:
    """★原子落盘：先写临时文件再改名，中断不会留下半截缓存。"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{name}.csv.gz"
    staging = target.with_suffix(".tmp")
    frame.to_csv(staging, index=False, compression="gzip")
    staging.replace(target)


#: ★★2026-07-21 B110 F002 实测的**新静默失败模式**（与 B109 的静默截断同型、方向相反）：
#: `income_vip` 在压力/限流下会**返回空表而不抛异常**。实测 `period=20191231,
#: report_type=2` 一次返回 0 行，间隔数秒后连续四次稳定返回 4,856 行；`20200630`
#: 同样 0 行 → 5,000 行。
#:
#: ★为什么它比抛异常危险得多：`fetch_paged` 的终止条件是**短页**，空的第一页
#: 与「这一期本来就没有数据」完全无法区分 → `report.failures` 为空、
#: `truncation_suspected` 为假、漏斗一切正常，而整整一期的数据凭空消失。
#: 若发生在 rt=1 上，该期所有证券的分量都会被记成 `COMPONENT_MISSING`，
#: 表现为「数据源的固有覆盖限制」——正是最难发现的那类污染。
#:
#: 防线：**行数下限 + 长退避重试 + 绝不缓存空表**。
_MIN_ROWS_ABORT = "abort"
_MIN_ROWS_DISCLOSE = "disclose"
_LONG_BACKOFF_SECONDS: tuple[float, ...] = (15.0, 30.0, 60.0, 120.0)


def _fetch_cached(
    pro: Any,
    endpoint_fn_name: str,
    *,
    cache_dir: Path,
    name: str,
    ledger: Ledger,
    min_rows: int = 0,
    on_shortfall: str = _MIN_ROWS_ABORT,
    **params: Any,
) -> pd.DataFrame:
    """走缓存的分页拉取。★重跑零成本是 F003/F004 反复迭代的前提。

    ``min_rows`` 是该端点的**行数下限**。低于它即视为拉取失败并长退避重试——
    见上方常量注释：空表在 `fetch_paged` 里与「本来就没数据」无法区分。
    ``on_shortfall`` 决定重试耗尽后是中止（取值源）还是如实披露（诊断源）。
    """
    hit = _cached(cache_dir, name)
    if hit is not None:
        return hit

    last_reason = ""
    seen_multiple: int | None = None
    for backoff in (0.0, *_LONG_BACKOFF_SECONDS):
        if backoff:
            time.sleep(backoff)
        frame, report = fetch_paged(getattr(pro, endpoint_fn_name), endpoint=name, **params)
        ledger.add(report)
        if report.failures:
            last_reason = f"failures={report.failures}"
            continue
        if len(frame) < min_rows:
            # ★绝不缓存空表/短表：一旦落盘，后续重跑会把这个洞变成「事实」。
            last_reason = f"rows={len(frame)} < min_rows={min_rows}（疑似静默空表）"
            continue
        if len(frame) and len(frame) % DEFAULT_PAGE_SIZE == 0:
            # ★★分页在**整页边界**停下。`fetch_paged` 的终止条件是短页，所以这只有
            # 两种可能：(a) 下一页真的是空的（数据恰好是页大小的整数倍），
            # (b) 下一页遭遇静默空响应 → **数据被悄悄截断**。
            # 实测 (b) 真实发生过 14 次（含 `daily_basic` 两日，把 2023 年初的
            # 分母砍到 5,000 只、覆盖率从 ~90% 压到 67.6%）。
            # 判别法：重取。随机截断重取会变，真整数倍则稳定不变。
            if seen_multiple == len(frame):
                break  # 两次一致 → 认定为真整数倍，接受并在 ledger 里留痕
            seen_multiple = len(frame)
            last_reason = f"rows={len(frame)} 恰为页大小整数倍（疑似分页被静默截断）"
            continue
        frame = _normalize(frame)
        _store(cache_dir, name, frame)
        time.sleep(_THROTTLE)
        return frame

    if seen_multiple is not None and len(frame) == seen_multiple:
        # 稳定的整数倍：接受，但必须可被 Codex 看见。
        report.truncation_suspected = True
        frame = _normalize(frame)
        _store(cache_dir, name, frame)
        return frame
    if on_shortfall == _MIN_ROWS_DISCLOSE:
        return pd.DataFrame()
    raise RuntimeError(f"拉取失败，拒绝用残缺数据继续: {name} {last_reason}")


def _filter_report_type(frame: pd.DataFrame, wanted: str, period: str) -> pd.DataFrame:
    """★必须 `.astype(str).str.strip()`；裸比较在 dtype 漂移时会整期静默归零。"""
    if frame.empty:
        return frame
    filtered = frame[frame["report_type"].astype(str).str.strip() == wanted]
    share = len(filtered) / max(len(frame), 1)
    if wanted == CONSOLIDATED and share < _RT1_SHARE_FLOOR:
        raise RuntimeError(f"report_type={wanted} 占比异常 {share:.1%} @ {period}")
    return filtered


def _versions_index(rows: Iterable[dict[str, Any]]) -> dict[str, list[FactVersion]]:
    index: dict[str, list[FactVersion]] = {}
    for version in build_versions(rows):
        index.setdefault(version.ts_code, []).append(version)
    return index


class _SecurityPeriodView(Mapping[str, list[FactVersion]]):
    """按 (期次 → 证券 → 版本) 的全局索引，切出**一只证券**的只读视图。

    ★不实体化：144 个月 × 5,000 只 × 54 期若每次都建字典，是 4×10⁷ 次插入，
    光这一步就能让全量跑从几分钟变成几十分钟（B109 `panel_cli.py:192` 有同型教训）。
    """

    __slots__ = ("_index", "_code", "_periods")

    def __init__(
        self,
        index: dict[str, dict[str, list[FactVersion]]],
        code: str,
        periods: tuple[str, ...],
    ) -> None:
        self._index = index
        self._code = code
        self._periods = periods

    def __getitem__(self, period: str) -> list[FactVersion]:
        return self._index.get(period, {}).get(self._code, [])

    def __iter__(self) -> Any:
        return iter(self._periods)

    def __len__(self) -> int:
        return len(self._periods)


def run(
    *,
    start: str,
    end: str,
    cache_dir: Path,
    out_dir: Path,
) -> dict[str, Any]:
    import tushare as ts  # noqa: PLC0415 - 延迟导入，离线单测不需要网络依赖

    pro = ts.pro_api(load_token())
    ledger = Ledger()
    cache_dir.mkdir(parents=True, exist_ok=True)

    # --- 宇宙（★三态全拉，且走分页；见模块 docstring 第 2 点）---
    stock_rows: list[dict[str, Any]] = []
    for status in ALL_LIST_STATUS:
        frame = _fetch_cached(
            pro,
            "stock_basic",
            cache_dir=cache_dir,
            name=f"stock_basic_{status}",
            ledger=ledger,
            # P 态实测为 0 只，故只对 L 设下限（实测 L=5,529）
            min_rows=3000 if status == "L" else 0,
            list_status=status,
            fields=STOCK_FIELDS,
        )
        stock_rows.extend(frame.to_dict("records"))
    securities = build_securities(stock_rows)
    malformed = len(stock_rows) - len(securities)  # H4：B109 未计此项

    # --- 交易日历（★一次性预取）---
    calendar = _fetch_cached(
        pro,
        "trade_cal",
        cache_dir=cache_dir,
        name="trade_cal",
        ledger=ledger,
        min_rows=3000,
        exchange="SSE",
        start_date="20120101",
        end_date="20250630",
    )
    open_days = sorted(
        str(value)
        for value in calendar.loc[calendar["is_open"].astype(str) == "1", "cal_date"]
    )

    # --- 网格：144 个形成日 + 1 个只用于取退出价的月末 ---
    formation_dates = month_end_dates(start, end)
    grid_natural = month_end_dates(start, _next_month(end))
    grid_trade: dict[str, str] = {}
    for natural in grid_natural:
        resolved = last_trade_date_on_or_before(open_days, natural)
        if resolved is None:
            raise RuntimeError(f"交易日历覆盖不到 {natural}")
        grid_trade[natural] = resolved

    # --- 财务：54 期，rt=1（取值）+ rt=2（R2 对拍）---
    periods = quarter_ends()
    versions_by_period: dict[str, dict[str, list[FactVersion]]] = {}
    direct_by_period: dict[str, dict[str, list[FactVersion]]] = {}
    retention: dict[str, float] = {}
    for period in periods:
        frame = _fetch_cached(
            pro,
            "income_vip",
            cache_dir=cache_dir,
            name=f"income_rt1_{period}",
            ledger=ledger,
            # ★取值源：低于下限即中止。A 股 2011 年起在市 ≥2,200 只，
            # 1,500 是留足余量后仍能识破「整期空表」的门槛。
            min_rows=1500,
            period=period,
            fields=INCOME_FIELDS,
        )
        rows = _filter_report_type(frame, CONSOLIDATED, period).to_dict("records")
        versions_by_period[period] = _versions_index(rows)
        retention[period] = flag0_retention(rows)

        direct = _fetch_cached(
            pro,
            "income_vip",
            cache_dir=cache_dir,
            name=f"income_rt2_{period}",
            ledger=ledger,
            # 诊断源（R2 对拍）：重试耗尽后如实披露为不可用，不中止全局。
            min_rows=1000,
            on_shortfall=_MIN_ROWS_DISCLOSE,
            period=period,
            report_type=DIRECT_QUARTER,
            fields=INCOME_FIELDS,
        )
        direct_rows = _filter_report_type(direct, DIRECT_QUARTER, period).to_dict("records")
        direct_by_period[period] = _versions_index(direct_rows)

    # --- 价格与市值：145 个网格交易日 ---
    prices: dict[str, dict[str, PricePoint]] = {}
    caps: dict[str, dict[str, Any]] = {}
    mv_missing_rows: dict[str, int] = {}
    for natural, trade_date in grid_trade.items():
        basic = _fetch_cached(
            pro,
            "daily_basic",
            cache_dir=cache_dir,
            name=f"daily_basic_{trade_date}",
            ledger=ledger,
            min_rows=1500,
            trade_date=trade_date,
            fields=BASIC_FIELDS,
        )
        factors = _fetch_cached(
            pro,
            "adj_factor",
            cache_dir=cache_dir,
            name=f"adj_factor_{trade_date}",
            ledger=ledger,
            min_rows=1500,
            trade_date=trade_date,
        )
        factor_by_code = {
            str(row["ts_code"]): row["adj_factor"] for row in factors.to_dict("records")
        }
        points: dict[str, PricePoint] = {}
        cap_points: dict[str, Any] = {}
        unusable = 0
        for row in basic.to_dict("records"):
            code = str(row["ts_code"])
            point = build_point(row)
            if point is None:
                unusable += 1
            else:
                cap_points[code] = point
            factor = factor_by_code.get(code)
            close = to_decimal(row.get("close"))
            if factor is not None and close is not None:
                adj = to_decimal(factor)
                if adj is not None:
                    points[code] = PricePoint(
                        ts_code=code, trade_date=trade_date, close=close, adj_factor=adj
                    )
        prices[natural] = points
        caps[natural] = cap_points
        mv_missing_rows[natural] = unusable

    # --- 退市终值（D6）---
    terminal = _fetch_terminal_prices(
        pro, securities, prices, grid_natural, cache_dir=cache_dir, ledger=ledger
    )

    delisted_ever = frozenset(
        item.ts_code for item in securities if item.delist_date
    )

    # --- 逐月装配 ---
    funnels: list[dict[str, Any]] = []
    previous_ttm: dict[str, Any] = {}
    step_violations = 0
    period_key = tuple(periods)
    # ★明细流式落盘：144 个月 × ~3,000 行若全部驻留内存，仅这一项就是数百 MB。
    detail_sink = _DetailSink(cache_dir / "ep_panel.csv.gz")
    for seq, formation_date in enumerate(formation_dates, start=1):
        month_started = time.monotonic()
        in_universe = universe_as_of(securities, formation_date)
        ahead = [item for item in grid_natural if item > formation_date]
        rows_out: list[EpPanelRow] = []
        for security in in_universe:
            code = security.ts_code
            ttm = compute_ttm(
                ts_code=code,
                formation_date=formation_date,
                versions_by_period=_SecurityPeriodView(versions_by_period, code, period_key),
                lookback_periods=periods,
                list_date=security.list_date,
                direct_versions_by_period=_SecurityPeriodView(
                    direct_by_period, code, period_key
                ),
            )
            if step_without_filing(
                previous_ttm.get(code),
                ttm,
                previous_formation_date=formation_dates[seq - 2] if seq > 1 else "",
            ):
                step_violations += 1
            previous_ttm[code] = ttm
            fwd = forward_return(
                ts_code=code,
                formation_date=formation_date,
                grid_ahead=ahead,
                prices_by_date=prices,
                terminal=terminal.get(code),
            )
            rows_out.append(
                EpPanelRow(
                    ts_code=code,
                    formation_date=formation_date,
                    ttm=ttm,
                    market_cap=caps[formation_date].get(code),
                    forward=fwd,
                    delisted_later=(
                        code in delisted_ever and security.delist_date > formation_date
                    ),
                )
            )

        funnel = build_ep_funnel(
            rows_out,
            universe_size=len(in_universe),
            formation_date=formation_date,
            malformed_security_rows=malformed if seq == 1 else 0,
            price_trade_date=grid_trade[formation_date],
            exit_trade_date=grid_trade[ahead[0]] if ahead else "",
        )
        funnel["universe"] = summarize_universe(securities, formation_date)
        funnel["market_cap"] = summarize_marketcap(caps[formation_date].values())
        funnel["returns"] = summarize_returns(
            [row.forward for row in rows_out if row.forward is not None],
            delisted_later=delisted_ever,
        )
        funnel["elapsed_seconds"] = round(time.monotonic() - month_started, 2)
        funnel["api_calls_this_month"] = 0  # 全部预取，逐月增量为 0（见成本留痕总表）
        funnel["api_rows_this_month"] = 0
        if not funnel_closes(funnel):
            raise RuntimeError(f"漏斗不闭合 @ {formation_date}——有未归类流失（H4）")
        funnels.append(funnel)

        for row in rows_out:
            # ★有 E/P 的、以及**无 E/P 但有前向收益**的都要落盘：后者是 D1 的
            # B-wide 基准样本。少了它就算不出 coverage_composition_effect，
            # 而那个数 >1.0pp 时 spec §4 的 INCONCLUSIVE_COVERAGE_LIMITED 档要触发。
            if row.has_ep or (row.forward is not None and row.forward.is_usable):
                detail_sink.write(_detail_row(row))

    detail_sink.close()
    _write_funnel_csv(out_dir / "B110-F002-monthly-funnel.csv", funnels)

    total_ambiguous = sum(int(item["fact_version_ambiguous"]) for item in funnels)
    return {
        "params": {
            "start": start,
            "end": end,
            "n_formation_dates": len(formation_dates),
            "n_periods": len(periods),
            "n_grid_dates": len(grid_natural),
            "delist_stubs": [str(stub) for stub in DELIST_STUBS],
        },
        "panel": summarize_panel(funnels),
        "disclosures": mandatory_disclosures(
            fact_version_ambiguous=total_ambiguous,
            flag0_retention_by_period=retention,
        ),
        # ★R1：TTM 变了却无新披露的次数。非 0 = as-of 漏进未来 / 锚点抖动。
        "ttm_step_without_filing": step_violations,
        "cost": ledger.as_dict(),
        "equivalence_note": (
            "等价式在精确算术下与单季求和恒等（见 docs/specs/"
            "B110-frozen-conventions-addendum.md §4），一致率不构成数据质量证据。"
            "分子的真校验是 R1 阶跃性与 R2 单季直报对拍。"
        ),
    }


def _shift_days(yyyymmdd: str, days: int) -> str:
    from datetime import date, timedelta  # noqa: PLC0415 - 局部使用

    base = date(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:8]))
    return (base + timedelta(days=days)).strftime("%Y%m%d")


def _next_month(yyyymm: str) -> str:
    year, month = int(yyyymm[:4]), int(yyyymm[4:6])
    return f"{year + 1}01" if month == 12 else f"{year}{month + 1:02d}"


def _fetch_terminal_prices(
    pro: Any,
    securities: Iterable[Any],
    prices: dict[str, dict[str, PricePoint]],
    grid_natural: list[str],
    *,
    cache_dir: Path,
    ledger: Ledger,
) -> dict[str, PricePoint]:
    """退市名的最后成交价 × 其在网格上最后一次出现的复权因子（附录 D6）。

    ★**不能**用 ``adj_factor`` 的最后一行当终点：实测 `600213.SH` 退市 20241017
    而因子一直派发到 20250814。濒死股不分红，末段因子恒定。
    """
    last_factor: dict[str, Decimal] = {}
    for natural in grid_natural:
        for code, point in prices.get(natural, {}).items():
            last_factor[code] = point.adj_factor

    out: dict[str, PricePoint] = {}
    for security in securities:
        if not security.delist_date:
            continue
        if security.ts_code not in last_factor:
            continue  # 网格上从未出现过 → 与本窗口无关
        # ★只要最后一根成交，不必拉全历史（实测全历史每股 2-10 秒 × 338 只）。
        # 「最后交易日 → 退市日」实测中位 7 天、最长 71 天，90 天窗口有充分余量；
        # 窗口内为空时回落到全历史，避免为省调用而丢掉终值。
        window_start = _shift_days(security.delist_date, -90)
        frame = _fetch_cached(
            pro,
            "daily",
            cache_dir=cache_dir,
            name=f"daily_terminal_{security.ts_code}",
            ledger=ledger,
            ts_code=security.ts_code,
            start_date=window_start,
            end_date=security.delist_date,
        )
        if frame.empty:
            frame = _fetch_cached(
                pro,
                "daily",
                cache_dir=cache_dir,
                name=f"daily_terminal_full_{security.ts_code}",
                ledger=ledger,
                ts_code=security.ts_code,
                start_date="20120101",
                end_date="20250630",
            )
        if frame.empty:
            continue
        last = frame.sort_values("trade_date").iloc[-1]
        close = to_decimal(last["close"])
        if close is None:
            continue
        out[security.ts_code] = PricePoint(
            ts_code=security.ts_code,
            trade_date=str(last["trade_date"]),
            close=close,
            adj_factor=last_factor[security.ts_code],
        )
    return out


def _detail_row(row: EpPanelRow) -> dict[str, Any]:
    forward = row.forward
    detail: dict[str, Any] = {
        "ts_code": row.ts_code,
        "formation_date": row.formation_date,
        # ★无 E/P 的行留空串而不是 "None"：下游用非空判定是否进入五分位样本池。
        "ep": "" if row.ep is None else str(row.ep),
        "ttm_cny": str(row.ttm.value),
        "total_mv_cny": str(row.market_cap.total_mv_cny) if row.market_cap else "",
        "anchor_end_date": row.ttm.anchor_end_date,
        "report_lag_days": row.report_lag_days,
        "delisted_later": int(row.delisted_later),
        "fwd_status": str(forward.status) if forward else "",
        "horizon_months": forward.horizon_months if forward else "",
    }
    for stub in DELIST_STUBS:
        value = forward.by_stub.get(str(stub)) if forward else None
        detail[f"fwd_ret_stub_{stub}"] = "" if value is None else str(value)
    return detail


class _DetailSink:
    """(证券 × 形成日) 明细的流式写出。F003 的输入，不入 git（``data/`` 已忽略）。"""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = gzip.open(  # noqa: SIM115 - 流式写出，生命周期由 close() 管
            path, "wt", newline="", encoding="utf-8"
        )
        self._writer: csv.DictWriter[str] | None = None

    def write(self, row: dict[str, Any]) -> None:
        if self._writer is None:
            self._writer = csv.DictWriter(self._handle, fieldnames=list(row))
            self._writer.writeheader()
        self._writer.writerow(row)

    def close(self) -> None:
        self._handle.close()


def _write_funnel_csv(path: Path, funnels: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=csv_header())
        writer.writeheader()
        for seq, funnel in enumerate(funnels, start=1):
            writer.writerow(funnel_to_csv_row(funnel, seq=seq))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B110 F002 月末 E/P 面板 + 覆盖漏斗")
    parser.add_argument("--start", default="201301")
    parser.add_argument("--end", default="202412")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/research/B110"))
    parser.add_argument("--out-dir", type=Path, default=Path("docs/audits"))
    parser.add_argument("--out", type=Path, default=Path("docs/audits/B110-F002-panel.json"))
    args = parser.parse_args(argv)

    result = run(
        start=args.start, end=args.end, cache_dir=args.cache_dir, out_dir=args.out_dir
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(to_jsonable(result), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    panel = result["panel"]
    cost = result["cost"]
    print(f"形成日数: {panel['n_formation_dates']}")
    print(f"进入分位覆盖（合并）: {panel['pooled_usable_fraction']:.2%}")
    print(f"最差单月: {panel['worst_month_usable_fraction']:.2%}")
    print(f"R1 阶跃违规: {result['ttm_step_without_filing']}")
    print(f"实测 API: {cost['api_calls_total']} 次 / {cost['api_rows_total']} 行 / "
          f"{cost['elapsed_seconds']}s")
    if cost["truncation_suspected"]:
        print(f"★★ 疑似触顶截断: {cost['truncation_suspected']}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
