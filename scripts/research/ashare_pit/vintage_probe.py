"""B109 F001 — Tushare `income_vip` 的 vintage 能力探针。

回答三问探针（`docs/audits/tushare-three-question-probe-2026-07-20.md` §3.1）留下的未决问题：

1. `update_flag=0` 行的保留率为何随期间波动？它是否由「修订到达」触发？
2. 季报 / 半年报的修订率与 vintage 保留（三问探针只测了年报，而 TTM 需四个连续单季）
3. 已知修订中有多少能真正做 as-of 重建

**只测量，不实现 resolver**（resolver 属 F002）。

用法::

    .venv/bin/python -m scripts.research.ashare_pit.vintage_probe --out docs/audits/xxx.json

凭据只从 ``.env.local`` 读（H6）；token 不得出现在输出、日志或任何产物里。
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
ENV_FILE = REPO_ROOT / ".env.local"

FIELDS = "ts_code,ann_date,f_ann_date,end_date,report_type,update_flag,n_income_attr_p"

# 合并报表本体。其它 report_type 是单季/母公司/调整表，混入会污染修订判定。
CONSOLIDATED_REPORT_TYPE = "1"

PERIOD_LABELS = {"0331": "Q1", "0630": "H1", "0930": "Q3", "1231": "FY"}

_MAX_ATTEMPTS = 3
_RETRY_SLEEP_SECONDS = 3.0
_THROTTLE_SECONDS = 0.6


def load_token() -> str:
    """只从 `.env.local` 读 token。缺失即失败，不回退到任何默认值。"""
    if not ENV_FILE.exists():
        raise RuntimeError(f"{ENV_FILE} 不存在——请先写入 TUSHARE_TOKEN=<token>")
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        if line.startswith("TUSHARE_TOKEN="):
            token = line.split("=", 1)[1].strip()
            if token:
                return token
    raise RuntimeError(f"{ENV_FILE} 中未找到非空的 TUSHARE_TOKEN")


def fetch_period(pro: Any, period: str) -> pd.DataFrame | None:
    """拉一期全市场合并利润表。失败返回 None（由调用方显式记录，不静默跳过）。"""
    for attempt in range(_MAX_ATTEMPTS):
        try:
            df = pro.income_vip(period=period, fields=FIELDS)
            return df[df["report_type"] == CONSOLIDATED_REPORT_TYPE].dropna(
                subset=["n_income_attr_p"]
            )
        except Exception:  # noqa: BLE001 - 有界重试，最终以 None 显式暴露
            if attempt + 1 < _MAX_ATTEMPTS:
                time.sleep(_RETRY_SLEEP_SECONDS * (attempt + 1))
    return None


def measure_period(df: pd.DataFrame, period: str) -> dict[str, Any]:
    """单期测量：flag=0 保留率、修订率、检出机制拆分、分组修订率。"""
    stocks = int(df["ts_code"].nunique())
    flags = df.groupby("ts_code")["update_flag"].apply(set)
    with_flag0 = {code for code, values in flags.items() if "0" in values}

    distinct = df.groupby("ts_code")["n_income_attr_p"].nunique()
    revised = set(distinct[distinct > 1].index)

    # 检出机制拆分：0/1 配对 vs 多条 flag=1。
    # 这一项决定「flag=0 缺失时是否就看不见修订」。
    by_pair = by_multi_flag1 = 0
    for code in revised:
        sub = df[df["ts_code"] == code]
        values0 = set(sub[sub["update_flag"] == "0"]["n_income_attr_p"])
        values1 = set(sub[sub["update_flag"] == "1"]["n_income_attr_p"])
        if values0 and values1 and values0 != values1:
            by_pair += 1
        elif len(values1) > 1:
            by_multi_flag1 += 1

    without_flag0 = stocks - len(with_flag0)
    return {
        "period": period,
        "report_type": PERIOD_LABELS.get(period[4:], "?"),
        "stocks": stocks,
        "flag0_retention": len(with_flag0) / stocks if stocks else 0.0,
        "revised": len(revised),
        "observed_revision_rate": len(revised) / stocks if stocks else 0.0,
        "detected_by_flag_pair": by_pair,
        "detected_by_multi_flag1": by_multi_flag1,
        # ★分组修订率是「观测下界 vs 可能真值」的关键：若 flag=0 组显著更高，
        # 说明缺 flag=0 的那部分存在观测盲区。
        "rate_within_flag0_group": (
            len(revised & with_flag0) / len(with_flag0) if with_flag0 else 0.0
        ),
        "rate_without_flag0_group": (
            len(revised - with_flag0) / without_flag0 if without_flag0 else 0.0
        ),
    }


def measure_reconstructability(df: pd.DataFrame) -> Counter:
    """已知修订中有多少能做 as-of 重建。

    可重建的判据：**每个不同的数值各自对应一个不同的 ``f_ann_date``**——
    只有这样才能按「取 ``f_ann_date <= 形成日`` 中最大的一条」还原当时可见的版本。
    多个数值共用同一个 ``f_ann_date`` 则无法分辨先后，必须 fail closed。
    """
    kinds: Counter = Counter()
    distinct = df.groupby("ts_code")["n_income_attr_p"].nunique()
    for code in distinct[distinct > 1].index:
        sub = df[df["ts_code"] == code]
        first_seen = sub.groupby("n_income_attr_p")["f_ann_date"].min()
        if first_seen.nunique() >= 2:
            kinds["as_of_reconstructable"] += 1
        elif sub["f_ann_date"].nunique() >= 2:
            kinds["f_ann_date_not_one_to_one"] += 1
        else:
            kinds["not_reconstructable_same_f_ann_date"] += 1
    return kinds


def run(years: list[int]) -> dict[str, Any]:
    import tushare as ts  # noqa: PLC0415 - 延迟导入，离线单测不需要网络依赖

    pro = ts.pro_api(load_token())
    periods = [f"{year}{md}" for year in years for md in PERIOD_LABELS]

    rows: list[dict[str, Any]] = []
    failed: list[str] = []
    kinds: Counter = Counter()

    for period in periods:
        df = fetch_period(pro, period)
        if df is None:
            failed.append(period)  # 显式记录，不静默跳过（H4）
            continue
        rows.append(measure_period(df, period))
        kinds.update(measure_reconstructability(df))
        time.sleep(_THROTTLE_SECONDS)

    table = pd.DataFrame(rows)
    total_stocks = int(table["stocks"].sum()) if not table.empty else 0
    total_revised = int(table["revised"].sum()) if not table.empty else 0
    total_known = sum(kinds.values())

    return {
        "periods_requested": periods,
        "periods_failed": failed,
        "per_period": rows,
        "by_report_type": (
            table.groupby("report_type")
            .agg(stocks=("stocks", "sum"), revised=("revised", "sum"))
            .assign(rate=lambda t: t["revised"] / t["stocks"])
            .reset_index()
            .to_dict("records")
            if not table.empty
            else []
        ),
        "observed_revision_rate_lower_bound": (
            total_revised / total_stocks if total_stocks else 0.0
        ),
        # 上界：假设「无 flag=0 组」的真实修订率与「有 flag=0 组」相同。
        # 这是**保守上界**——flag=0 组很可能本就富集了修订，故真值应在两者之间。
        "revision_rate_upper_bound": (
            float(table["rate_within_flag0_group"].mean()) if not table.empty else 0.0
        ),
        "reconstructability": dict(kinds),
        "reconstructable_fraction": (
            kinds["as_of_reconstructable"] / total_known if total_known else 0.0
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B109 F001 Tushare vintage 探针（只测量）")
    parser.add_argument("--years", type=str, default="2021,2022,2023,2024")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)

    result = run([int(y) for y in args.years.split(",") if y.strip()])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(f"观测修订率（下界）: {result['observed_revision_rate_lower_bound']:.3%}")
    print(f"修订率上界（保守）: {result['revision_rate_upper_bound']:.2%}")
    print(f"已知修订可 as-of 重建比例: {result['reconstructable_fraction']:.1%}")
    if result["periods_failed"]:
        print(f"★ 拉取失败的期间（未计入统计）: {result['periods_failed']}")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
