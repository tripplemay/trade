"""F003 G-C — 分母身份独立复算 + H2 边界 + H1 真实数据量化。

★独立性：本脚本**自己算** |close*total_share - total_mv| / total_mv，
不调用 marketcap.identity_error 得出结论；随后再与 marketcap.build_point 对拍，
确认被审计模块与独立算法一致（两者不一致即为缺陷）。
"""

from __future__ import annotations

import json
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

import tushare as ts

from scripts.research.ashare_pit.fetch import fetch_paged
from scripts.research.ashare_pit.marketcap import (
    IDENTITY_SEVERE,
    IDENTITY_TOLERANCE,
    WAN_TO_CNY,
    build_point,
)
from scripts.research.ashare_pit.resolver import build_versions, resolve_as_of
from scripts.research.ashare_pit.vintage_probe import FIELDS, load_token

OUT = Path("/private/tmp/claude-501/-Users-yixingzhou-project-trade/f003")
pro = ts.pro_api(load_token())

BASIC_FIELDS = "ts_code,trade_date,close,total_share,float_share,total_mv,circ_mv,turnover_rate"
# 跨 11 年取样，含 F001 指出的分母薄弱年份 2014
TRADE_DATES = ["20141231", "20151231", "20181228", "20201231", "20211231", "20231229", "20250630"]

report_rows = []
for trade_date in TRADE_DATES:
    df, rep = fetch_paged(
        pro.daily_basic, endpoint="daily_basic", trade_date=trade_date, fields=BASIC_FIELDS
    )
    if df.empty:
        print(f"{trade_date}: EMPTY (非交易日?) failures={rep.failures}")
        continue
    rows = df.to_dict("records")

    n = 0
    within_tol = 0
    severe = 0
    errors = []
    mismatch_vs_module = 0
    circ_mv_would_pass = 0

    for row in rows:
        close = row.get("close")
        share = row.get("total_share")
        mv = row.get("total_mv")
        if close is None or share is None or mv is None:
            continue
        try:
            close_d, share_d, mv_d = Decimal(str(close)), Decimal(str(share)), Decimal(str(mv))
        except Exception:  # noqa: BLE001
            continue
        if mv_d <= 0:
            continue
        n += 1
        # ★独立算式
        err = abs(close_d * share_d - mv_d) / mv_d
        errors.append(err)
        if err <= IDENTITY_TOLERANCE:
            within_tol += 1
        if err > IDENTITY_SEVERE:
            severe += 1

        # 与被审计模块对拍
        point = build_point(row)
        if point is None:
            mismatch_vs_module += 1
        else:
            module_pass = point.is_usable
            if module_pass != (err <= IDENTITY_TOLERANCE):
                mismatch_vs_module += 1
            # 单位转换核对
            if point.total_mv_cny != mv_d * WAN_TO_CNY:
                mismatch_vs_module += 1

        # H2：若误用流通市值，身份还成立吗？（应大面积不成立 → 证明二者不可互换）
        circ = row.get("circ_mv")
        if circ is not None:
            circ_d = Decimal(str(circ))
            if circ_d > 0 and abs(close_d * share_d - circ_d) / circ_d <= IDENTITY_TOLERANCE:
                circ_mv_would_pass += 1

    errors.sort()
    median = errors[len(errors) // 2] if errors else Decimal(0)
    p99 = errors[int(len(errors) * 0.99)] if errors else Decimal(0)
    entry = {
        "trade_date": trade_date,
        "n": n,
        "pages": rep.pages,
        "within_0.5pct": within_tol,
        "within_0.5pct_frac": float(within_tol / n) if n else 0.0,
        "severe_gt_5pct": severe,
        "median_error": str(median),
        "p99_error": str(p99),
        "max_error": str(errors[-1]) if errors else "0",
        "module_disagreements": mismatch_vs_module,
        "circ_mv_identity_would_pass": circ_mv_would_pass,
        "circ_mv_identity_pass_frac": float(circ_mv_would_pass / n) if n else 0.0,
    }
    report_rows.append(entry)
    print(
        f"{trade_date}: n={n} pages={rep.pages} <=0.5%={within_tol} "
        f"({within_tol / n:.4%}) >5%={severe} median={median} p99={p99} "
        f"module_disagree={mismatch_vs_module} circMV_pass={circ_mv_would_pass}"
    )

# ---------- H1 真实数据量化：用 ann_date 替代会改变多少证券的结果 ----------
df, _ = fetch_paged(pro.income_vip, endpoint="income_vip", period="20211231", fields=FIELDS)
rows = df[df["report_type"] == "1"].to_dict("records")
by_code = defaultdict(list)
for row in rows:
    by_code[row["ts_code"]].append(row)

FORMATION = "20220630"
differ = 0
ambiguous_under_anndate = 0
checked = 0
for _code, items in by_code.items():
    v_f = build_versions(items)
    if not v_f:
        continue
    v_a = [
        type(v)(v.ts_code, v.end_date, v.ann_date, v.ann_date, v.update_flag, v.value)
        for v in v_f
        if v.ann_date
    ]
    if not v_a:
        continue
    checked += 1
    a = resolve_as_of(v_f, FORMATION)
    b = resolve_as_of(v_a, FORMATION)
    if str(a.status) != str(b.status) or a.value != b.value:
        differ += 1
    if str(b.status) == "FACT_VERSION_AMBIGUOUS" and str(a.status) == "RESOLVED":
        ambiguous_under_anndate += 1

print(
    f"\n[H1 真实数据] 形成日 {FORMATION} / 2021FY：检验 {checked} 只，"
    f"改用 ann_date 会改变结果的 = {differ} ({differ / checked:.2%})，"
    f"其中被打成 AMBIGUOUS 的 = {ambiguous_under_anndate}"
)

(OUT / "gc-results.json").write_text(
    json.dumps(
        {
            "identity": report_rows,
            "h1_real_data": {
                "formation_date": FORMATION,
                "period": "20211231",
                "checked": checked,
                "differ_under_ann_date": differ,
                "ambiguous_under_ann_date": ambiguous_under_anndate,
            },
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
