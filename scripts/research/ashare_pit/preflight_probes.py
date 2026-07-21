"""B110 全量跑之前的三个前置探针（P1/P2/P3），合计 <30 次调用。

P1 最关键：daily_basic.total_share 若不是 PIT（用今日股本回填历史），
分母作废、740 次调用全废，而 marketcap.identity_error 对此**零功率**
（total_mv 本身是 close×total_share 的派生量，回填会同时回填两边）。
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, "/Users/yixingzhou/project/trade")

import tushare as ts  # noqa: E402

from scripts.research.ashare_pit.fetch import fetch_paged  # noqa: E402
from scripts.research.ashare_pit.universe import (  # noqa: E402
    ALL_LIST_STATUS,
    build_securities,
    universe_as_of,
)
from scripts.research.ashare_pit.vintage_probe import load_token  # noqa: E402

pro = ts.pro_api(load_token())
out: dict[str, object] = {}
calls = 0


def p1_total_share_is_pit() -> dict[str, object]:
    """总股本是否随时间阶跃，且跳变是否与复权因子变化同日。"""
    global calls
    codes = [
        "600519.SH",  # 贵州茅台
        "000002.SZ",  # 万科A（多次送转）
        "002714.SZ",  # 牧原股份（多次定增+送转）
        "600036.SH",  # 招商银行（配股/转增）
        "000651.SZ",  # 格力电器（多次送转）
        "601398.SH",  # 工商银行
    ]
    findings = []
    for code in codes:
        db, rep = fetch_paged(
            pro.daily_basic,
            endpoint="daily_basic_hist",
            ts_code=code,
            start_date="20130101",
            end_date="20241231",
            fields="trade_date,total_share,close,total_mv",
        )
        calls += rep.pages
        time.sleep(0.4)
        af, rep2 = fetch_paged(
            pro.adj_factor,
            endpoint="adj_factor_hist",
            ts_code=code,
            start_date="20130101",
            end_date="20241231",
        )
        calls += rep2.pages
        time.sleep(0.4)
        if db.empty:
            findings.append({"ts_code": code, "error": "no daily_basic rows"})
            continue
        db = db.sort_values("trade_date").reset_index(drop=True)
        shares = db["total_share"].astype(float)
        jumps = []
        for i in range(1, len(db)):
            prev, cur = shares.iloc[i - 1], shares.iloc[i]
            if prev > 0 and abs(cur - prev) / prev > 0.001:
                jumps.append(
                    {
                        "date": str(db["trade_date"].iloc[i]),
                        "from": prev,
                        "to": cur,
                        "ratio": round(cur / prev, 4),
                    }
                )
        factor_change_dates: set[str] = set()
        if not af.empty:
            af = af.sort_values("trade_date").reset_index(drop=True)
            fac = af["adj_factor"].astype(float)
            for i in range(1, len(af)):
                if abs(fac.iloc[i] - fac.iloc[i - 1]) > 1e-9:
                    factor_change_dates.add(str(af["trade_date"].iloc[i]))
        aligned = sum(1 for j in jumps if j["date"] in factor_change_dates)
        findings.append(
            {
                "ts_code": code,
                "n_rows": len(db),
                "distinct_total_share": int(shares.nunique()),
                "first_total_share": float(shares.iloc[0]),
                "last_total_share": float(shares.iloc[-1]),
                "n_jumps": len(jumps),
                "n_jumps_on_adj_factor_change_day": aligned,
                "n_adj_factor_changes": len(factor_change_dates),
                "first_5_jumps": jumps[:5],
            }
        )
    constant = [f for f in findings if f.get("distinct_total_share") == 1]
    return {
        "verdict": "BACKFILLED_NOT_PIT" if len(constant) == len(findings) else "VARIES_OVER_TIME",
        "n_constant_series": len(constant),
        "findings": findings,
    }


def p2_income_vip_accepts_report_type() -> dict[str, object]:
    global calls
    df, rep = fetch_paged(
        pro.income_vip,
        endpoint="income_vip_rt2",
        period="20230930",
        report_type="2",
        fields="ts_code,end_date,report_type,f_ann_date,n_income_attr_p",
    )
    calls += rep.pages
    time.sleep(0.4)
    if df.empty:
        return {"accepted": False, "rows": 0, "failures": rep.failures}
    dist = df["report_type"].astype(str).str.strip().value_counts().to_dict()
    return {
        "accepted": set(dist) == {"2"},
        "rows": int(len(df)),
        "report_type_distribution": {str(k): int(v) for k, v in dist.items()},
        "pages": rep.pages,
    }


def p3_universe_size() -> dict[str, object]:
    global calls
    rows: list[dict[str, object]] = []
    for status in ALL_LIST_STATUS:
        df, rep = fetch_paged(
            pro.stock_basic,
            endpoint=f"stock_basic:{status}",
            list_status=status,
            fields="ts_code,symbol,name,list_status,list_date,delist_date",
        )
        calls += rep.pages
        time.sleep(0.4)
        rows.extend(df.to_dict("records"))
    securities = build_securities(rows)
    return {
        "raw_rows": len(rows),
        "securities": len(securities),
        "in_universe_20130131": len(universe_as_of(securities, "20130131")),
        "in_universe_20241231": len(universe_as_of(securities, "20241231")),
        "delisted_flagged": sum(1 for s in securities if s.is_delisted),
    }


out["P1_total_share_pit"] = p1_total_share_is_pit()
out["P2_income_vip_report_type"] = p2_income_vip_accepts_report_type()
out["P3_universe"] = p3_universe_size()
out["total_api_pages"] = calls

path = Path(sys.argv[1])
path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out["P1_total_share_pit"], ensure_ascii=False, indent=2)[:3000])
print("---P2---")
print(json.dumps(out["P2_income_vip_report_type"], ensure_ascii=False))
print("---P3---")
print(json.dumps(out["P3_universe"], ensure_ascii=False))
print(f"pages={calls} -> {path}")
