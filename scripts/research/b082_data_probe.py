"""B082 F001 — dividend-lowvol data-reality probe (GO / NO-GO gate).

Real akshare fetches (no fakes) measuring coverage / depth / freshness of the four
series the B082 defensive sleeve needs:

1. 512890 (华泰柏瑞中证红利低波动 ETF) daily bars — the tradeable instrument;
2. H30269 (中证红利低波动指数) history — the longer secondary (no-cost口径);
3. H30269 dividend yield (中证指数官网估值) — the numerator of the spread signal;
4. China 10Y treasury yield — the denominator of the spread signal.

GO requires: ETF bars usable, AND both spread-signal series >= 5y deep (spec §2 F001 —
the spread rule needs a rate history long enough to cover a regime cycle). Honest
NO-GO stops the batch (B077 discipline).

Output: JSON to stdout + optional --out-json. The evaluator re-runs this standalone
(deterministic shape, live data — depths can only grow).

Usage: .venv/bin/python scripts/research/b082_data_probe.py [--out-json PATH]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from typing import Any

MIN_SIGNAL_YEARS = 5.0
_TODAY = dt.date.today()


def _series_summary(dates: list[dt.date], label: str) -> dict[str, Any]:
    if not dates:
        return {"series": label, "ok": False, "rows": 0, "error": "empty"}
    first, last = min(dates), max(dates)
    years = (last - first).days / 365.25
    staleness = (_TODAY - last).days
    return {
        "series": label,
        "ok": True,
        "rows": len(dates),
        "first": first.isoformat(),
        "last": last.isoformat(),
        "depth_years": round(years, 2),
        "staleness_days": staleness,
    }


def _coerce_dates(values: Any) -> list[dt.date]:
    out: list[dt.date] = []
    for v in values:
        if isinstance(v, dt.datetime):
            out.append(v.date())
        elif isinstance(v, dt.date):
            out.append(v)
        else:
            try:
                out.append(dt.date.fromisoformat(str(v)[:10]))
            except ValueError:
                continue
    return out


def probe(out_json: str | None) -> int:
    import akshare  # heavy import, real network below

    results: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    # 1) ETF 512890 daily — sina host (VM-reachable, B068 §23 family). The eastmoney
    # fund_etf_hist_em route SSL-fails off-box (probe round 1, recorded in the
    # data-reality report); sina bars are UNADJUSTED (no dividend) — which is why the
    # TR index (H20269) is the primary return口径 and the ETF is the
    # implementability/cost layer only.
    try:
        df = akshare.fund_etf_hist_sina(symbol="sh512890")
        results.append(_series_summary(_coerce_dates(df["date"]), "etf_512890_daily_sina"))
    except Exception as exc:  # noqa: BLE001 — probe records, never raises
        errors["etf_512890_daily_sina"] = f"{type(exc).__name__}: {exc}"

    # 2a/2b) Index price (H30269) + TOTAL RETURN (H20269 红利低波全收益) histories
    # (中证指数官网). The TR−PR growth spread backs out the index's own dividend-yield
    # series (13.5y deep) — the spread signal's numerator; csindex's valuation
    # endpoint only returns ~1 month of股息率 (probe round 1 dead end).
    for code, label in (("H30269", "index_h30269_price"), ("H20269", "index_h20269_totalreturn")):
        try:
            df = akshare.stock_zh_index_hist_csindex(
                symbol=code,
                start_date="20050101",
                end_date=_TODAY.strftime("%Y%m%d"),
            )
            results.append(_series_summary(_coerce_dates(df["日期"]), label))
        except Exception as exc:  # noqa: BLE001
            errors[label] = f"{type(exc).__name__}: {exc}"

    # 3) Market-level dividend yield (legulegu) — 21.5y secondary/robustness proxy.
    try:
        df = akshare.stock_a_gxl_lg(symbol="上证A股")
        results.append(_series_summary(_coerce_dates(df["日期"]), "gxl_sh_a_market"))
    except Exception as exc:  # noqa: BLE001
        errors["gxl_sh_a_market"] = f"{type(exc).__name__}: {exc}"

    # 4) China 10Y treasury yield (chinabond via akshare).
    try:
        df = akshare.bond_zh_us_rate(start_date="20050101")
        col = "中国国债收益率10年"
        sub = df[["日期", col]].dropna()
        summary = _series_summary(_coerce_dates(sub["日期"]), "cn_treasury_10y")
        summary["value_column"] = col
        results.append(summary)
    except Exception as exc:  # noqa: BLE001
        errors["cn_treasury_10y"] = f"{type(exc).__name__}: {exc}"

    by_label = {r["series"]: r for r in results}

    def _depth(label: str) -> float:
        row = by_label.get(label)
        return float(row["depth_years"]) if row and row.get("ok") else 0.0

    etf_ok = by_label.get("etf_512890_daily_sina", {}).get("ok", False)
    # Yield numerator = TR−PR derived series: needs BOTH index legs >= 5y.
    yield_ok = (
        _depth("index_h30269_price") >= MIN_SIGNAL_YEARS
        and _depth("index_h20269_totalreturn") >= MIN_SIGNAL_YEARS
    )
    rate_ok = _depth("cn_treasury_10y") >= MIN_SIGNAL_YEARS
    verdict = "GO" if (etf_ok and yield_ok and rate_ok) else "NO-GO"

    payload = {
        "probe": "B082-F001 dividend-lowvol data reality",
        "as_of": _TODAY.isoformat(),
        "akshare_version": akshare.__version__,
        "min_signal_years": MIN_SIGNAL_YEARS,
        "series": results,
        "errors": errors,
        "gates": {
            "etf_bars_usable": bool(etf_ok),
            "trpr_yield_legs_ge_5y": bool(yield_ok),
            "treasury_10y_ge_5y": bool(rate_ok),
        },
        "verdict": verdict,
    }
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    print(text)
    if out_json:
        with open(out_json, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    return 0 if verdict == "GO" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-json", default=None)
    args = parser.parse_args()
    return probe(args.out_json)


if __name__ == "__main__":
    sys.exit(main())
