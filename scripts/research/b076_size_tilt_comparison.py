#!/usr/bin/env python
"""B076 F001 — size-tilt controlled sweep: does tilting toward small-caps help?

Answers the batch's question (spec §0): the B075 wide universe did NOT change cn_attack's
selection (top-25 stayed blue-chip, paper rebalanced=0) because the composite tilts large.
A parameterised **small-cap size factor** (``size_tilt_weight``) can push selection toward
small/mid-caps — but **does the tilt earn its risk?** This sweeps the tilt over
``{current=0, light, medium, strong}`` and reports, per level: CAGR / Sharpe / max DD /
turnover (walk-forward IS/OOS) PLUS the **small-cap breadth** the tilt is supposed to buy
(selected-basket median cap, cap-percentile within the universe, seed-43 overlap, small-cap
fraction). The verdict is verdict-gated (B069 NO-SWITCH precedent): GO only if some tilt is
**risk-adjusted not-worse AND genuinely adds breadth**; else NO-GO (honest, don't ship a
worse strategy just to "use" the wide pool).

Two cuts, both real numbers:

* **Primary — de-biased** (``pure_momentum`` on the B070 survivorship-free PIT universe,
  1310 names incl. delisted, + ``cn_size.csv`` PIT circ-cap). This is the clean experiment:
  small-cap survivorship bias is heaviest, so the de-biased universe is mandatory (spec §0).
  pure_momentum needs no fundamentals — which delisted names lack — so it is the variant that
  CAN be fully de-biased (matches B070 F003's choice).
* **Secondary — survivor-biased, labelled** (``quality_momentum`` on the B068 current-top-N
  universe, which already carries fundamentals + circ-cap). Free quality fundamentals do not
  exist for delisted names, so this variant cannot be de-biased; it is a directional check
  that the tilt behaves with quality in the blend, NOT gating evidence. Its survivorship bias
  flatters small-caps (delisted small-cap losers absent), so a NO-GO here is doubly damning.

Reads only research data roots; the production root (B075's live wide surface) is untouched.
Pure ``trade`` (no akshare/baostock) — runs anywhere the research CSVs are present.

Usage::

    .venv/bin/python scripts/research/b076_size_tilt_comparison.py \
        --b070-root data/research/b070 --b070-size data/research/b076/cn_size.csv \
        --b068-root data/research/b068 \
        --out-md docs/test-reports/B076-size-tilt-comparison.md \
        --out-json data/research/b076/f001_size_tilt_comparison.json
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from trade.strategies.cn_attack_momentum_quality.parameters import (
    FACTOR_VARIANT_PURE_MOMENTUM,
    FACTOR_VARIANT_QUALITY_MOMENTUM,
    WEIGHTING_SCHEME_EQUAL,
    CnAttackParameters,
)

# Size-tilt sweep grid (spec §2: 0=current / light / medium / strong).
SIZE_TILT_LEVELS: dict[str, float] = {
    "current": 0.0,
    "light": 0.15,
    "medium": 0.30,
    "strong": 0.50,
}
_IN_SAMPLE_FRACTION = 0.7  # walk-forward split (matches B070 comparison)

# GO thresholds (deterministic verdict): a tilt must be OOS-Sharpe not-worse than current
# (within tol) AND add real breadth (more small-caps AND a meaningfully smaller basket).
_SHARPE_TOL = 0.05
_SMALL_CAP_FRAC_GAIN = 0.15
_CAP_PCTILE_DROP = 0.10


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="B076 F001 size-tilt sweep + verdict")
    parser.add_argument("--b070-root", type=Path, required=True, help="de-biased research root")
    parser.add_argument("--b070-size", type=Path, required=True, help="cn_size.csv (PIT circ-cap)")
    parser.add_argument("--b068-root", type=Path, default=None, help="survivor root (2nd cut)")
    parser.add_argument("--out-md", type=Path, required=True)
    parser.add_argument("--out-json", type=Path, required=True)
    parser.add_argument("--start", type=_parse_date, default=date(2019, 4, 1))
    parser.add_argument("--end", type=_parse_date, default=None)
    return parser.parse_args(argv)


# --------------------------------------------------------------------------- #
# market-cap loading (schema-tolerant + month-end downsample for a light hot loop)
# --------------------------------------------------------------------------- #
def load_marketcap(path: Path) -> pd.DataFrame:
    """Read a market-cap CSV → ``data_date,ticker,market_cap`` (month-end downsampled).

    Accepts either the B076 ``cn_size.csv`` (``market_cap`` = PIT circ cap, already
    month-end) or the B068 ``cn_marketcap.csv`` (``circ_mv`` daily). Downsamples to the
    last observation per ticker per calendar month so the daily signal's PIT lookup stays
    cheap regardless of source granularity."""
    frame = pd.read_csv(path)
    if "market_cap" not in frame.columns:
        if "circ_mv" in frame.columns:
            frame = frame.rename(columns={"circ_mv": "market_cap"})
        else:
            raise ValueError(f"{path}: no market_cap / circ_mv column")
    frame = frame.loc[:, ["data_date", "ticker", "market_cap"]].copy()
    frame["data_date"] = pd.to_datetime(frame["data_date"])
    frame["_ym"] = frame["data_date"].dt.to_period("M")
    frame = frame.sort_values(["ticker", "data_date"], kind="mergesort")
    frame = frame.groupby(["ticker", "_ym"], sort=False).last().reset_index()
    return frame.loc[:, ["data_date", "ticker", "market_cap"]]


def latest_caps(marketcap: pd.DataFrame, as_of: date) -> pd.Series:
    """Per-ticker latest ``market_cap`` on/before ``as_of`` (raw CNY, for breadth stats)."""
    visible = marketcap.loc[marketcap["data_date"] <= pd.Timestamp(as_of)]
    if visible.empty:
        return pd.Series(dtype="float64")
    visible = visible.sort_values(["ticker", "data_date"], kind="mergesort")
    return visible.groupby("ticker", sort=False).last()["market_cap"]


# --------------------------------------------------------------------------- #
# breadth metrics — quantify whether the tilt REALLY pulls smaller names in
# --------------------------------------------------------------------------- #
def breadth_metrics(
    selected: tuple[str, ...],
    universe_caps: pd.Series,
    seed_set: frozenset[str],
) -> dict[str, Any]:
    """Small-cap breadth of the selected basket vs the universe cap cross-section.

    ``universe_caps`` is the latest cap per universe name at the as-of date. Reports:
    median selected cap (CNY); median cap-percentile within the universe (0=smallest,
    1=biggest — LOWER means a smaller-cap basket); seed-43 overlap fraction; and small-cap
    fraction (selected names below the universe median cap)."""
    n = len(selected)
    sel_caps = universe_caps.reindex(list(selected)).dropna()
    if universe_caps.empty or sel_caps.empty:
        return {
            "selected_count": n,
            "median_selected_cap_bn": None,
            "median_cap_pctile": None,
            "seed43_overlap_frac": round(len(set(selected) & seed_set) / n, 3) if n else None,
            "small_cap_frac": None,
        }
    pctile = universe_caps.rank(pct=True)  # 0..1, smallest→~0
    universe_median = float(universe_caps.median())
    small = sum(1 for cap in sel_caps if cap < universe_median)
    return {
        "selected_count": n,
        "median_selected_cap_bn": round(float(sel_caps.median()) / 1e9, 2),
        "median_cap_pctile": round(float(pctile.reindex(sel_caps.index).median()), 3),
        "seed43_overlap_frac": round(len(set(selected) & seed_set) / n, 3),
        "small_cap_frac": round(small / len(sel_caps), 3),
    }


# --------------------------------------------------------------------------- #
# one backtest run → full + IS/OOS metrics + breadth
# --------------------------------------------------------------------------- #
def _segment_metrics(curve: pd.DataFrame) -> dict[str, Any]:
    from trade.backtest.us_quality_momentum.metrics import (
        annualized_return,
        max_drawdown,
        sharpe_ratio,
    )

    def _seg(lo: Any, hi: Any) -> tuple[float, float, float]:
        seg = curve[(curve["date"] >= lo) & (curve["date"] <= hi)].reset_index(drop=True)
        if len(seg) < 2:
            return 0.0, 0.0, 0.0
        rets = seg.set_index("date")["equity"].pct_change().dropna()
        return annualized_return(seg), sharpe_ratio(rets), max_drawdown(seg)

    if len(curve) < 4:
        return {
            "is_split_date": None, "is_sharpe": 0.0,
            "oos_cagr": 0.0, "oos_sharpe": 0.0, "oos_max_drawdown": 0.0,
        }
    dates = curve["date"].tolist()
    idx = max(1, min(len(dates) - 2, int(len(dates) * _IN_SAMPLE_FRACTION)))
    split = pd.Timestamp(dates[idx])
    first, last = pd.Timestamp(curve["date"].iloc[0]), pd.Timestamp(curve["date"].iloc[-1])
    _, is_sharpe, _ = _seg(first, split)
    oos_cagr, oos_sharpe, oos_dd = _seg(split, last)
    return {
        "is_split_date": split.date().isoformat(),
        "is_sharpe": round(is_sharpe, 3),
        "oos_cagr": round(oos_cagr, 4),
        "oos_sharpe": round(oos_sharpe, 3),
        "oos_max_drawdown": round(oos_dd, 4),
    }


def run_one(
    level_name: str,
    tilt: float,
    variant: str,
    *,
    prices: pd.DataFrame,
    marketcap: pd.DataFrame | None,
    fundamentals: pd.DataFrame | None,
    universe_history: dict[date, tuple[str, ...]],
    start: date,
    end: date | None,
    seed_set: frozenset[str],
) -> dict[str, Any]:
    from trade.backtest.cn_attack_momentum_quality.engine import run_cn_attack_backtest

    params = CnAttackParameters(
        factor_variant=variant,
        weighting_scheme=WEIGHTING_SCHEME_EQUAL,
        size_tilt_weight=tilt,
    )
    result = run_cn_attack_backtest(
        params,
        start=start,
        end=end,
        prices=prices,
        fundamentals=fundamentals,
        marketcap=marketcap if tilt > 0 else None,
        universe_history=universe_history,
    )
    curve = result.equity_curve
    end_date = curve["date"].iloc[-1].date()
    selected = tuple(ticker for ticker, _ in result.final_holdings.weights)
    if marketcap is not None and not marketcap.empty:
        universe_caps = latest_caps(marketcap, end_date)
    else:
        universe_caps = pd.Series(dtype="float64")
    breadth = breadth_metrics(selected, universe_caps, seed_set)

    row: dict[str, Any] = {
        "level": level_name,
        "size_tilt_weight": tilt,
        "variant": variant,
        "rebalance_count": result.rebalance_count,
        "full_cagr": round(result.metrics.annualized_return, 4),
        "full_sharpe": round(result.metrics.sharpe_ratio, 3),
        "full_max_drawdown": round(result.metrics.max_drawdown, 4),
        "turnover": round(result.total_turnover, 2),
        "total_cost": round(result.total_cost, 2),
        **_segment_metrics(curve),
        **breadth,
    }
    return row


def run_sweep(
    variant: str,
    *,
    prices: pd.DataFrame,
    marketcap: pd.DataFrame | None,
    fundamentals: pd.DataFrame | None,
    universe_history: dict[date, tuple[str, ...]],
    start: date,
    end: date | None,
    seed_set: frozenset[str],
) -> list[dict[str, Any]]:
    return [
        run_one(
            name, tilt, variant,
            prices=prices, marketcap=marketcap, fundamentals=fundamentals,
            universe_history=universe_history, start=start, end=end, seed_set=seed_set,
        )
        for name, tilt in SIZE_TILT_LEVELS.items()
    ]


# --------------------------------------------------------------------------- #
# verdict — deterministic GO/NO-GO (unit-tested); verdict-gated (B069 precedent)
# --------------------------------------------------------------------------- #
def judge_size_tilt(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """GO only if a tilt is OOS-Sharpe not-worse than current AND adds real breadth.

    ``rows[0]`` is the current (tilt=0) baseline. For each tilt > 0:
      * risk_adjusted_ok = oos_sharpe >= current.oos_sharpe - tol;
      * adds_breadth      = small_cap_frac >= current + gain AND cap_pctile <= current - drop.
    GO → the qualifying tilt with the best OOS Sharpe. Otherwise NO-GO with a reason that
    classifies WHY (all tilts risk-worse / no real breadth / breadth only at a Sharpe cost).
    """
    current = rows[0]
    cur_sharpe = current["oos_sharpe"]
    cur_small = current.get("small_cap_frac")
    cur_pctile = current.get("median_cap_pctile")

    qualifying: list[dict[str, Any]] = []
    any_breadth = False
    any_risk_ok = False
    for row in rows[1:]:
        small = row.get("small_cap_frac")
        pctile = row.get("median_cap_pctile")
        risk_ok = row["oos_sharpe"] >= cur_sharpe - _SHARPE_TOL
        breadth_ok = (
            small is not None
            and cur_small is not None
            and pctile is not None
            and cur_pctile is not None
            and small >= cur_small + _SMALL_CAP_FRAC_GAIN
            and pctile <= cur_pctile - _CAP_PCTILE_DROP
        )
        any_risk_ok = any_risk_ok or risk_ok
        any_breadth = any_breadth or breadth_ok
        if risk_ok and breadth_ok:
            qualifying.append(row)

    if qualifying:
        winner = max(qualifying, key=lambda r: r["oos_sharpe"])
        return {
            "verdict": "GO",
            "winning_level": winner["level"],
            "winning_size_tilt_weight": winner["size_tilt_weight"],
            "reason": (
                f"size_tilt={winner['size_tilt_weight']} ({winner['level']}) is OOS-Sharpe "
                f"not-worse than current ({winner['oos_sharpe']} vs {cur_sharpe}) AND genuinely "
                f"adds small-cap breadth (small_cap_frac {winner['small_cap_frac']} vs "
                f"{cur_small}; cap_pctile {winner['median_cap_pctile']} vs {cur_pctile})."
            ),
        }

    if not any_breadth:
        reason = (
            "NO tilt level produced a materially smaller-cap basket (the wide universe's "
            "small names still rank too low on momentum/quality to be selected) — the size "
            "factor does not meaningfully change selection; tilting only adds churn/risk."
        )
    elif not any_risk_ok:
        reason = (
            "Every tilt that added breadth was OOS-Sharpe WORSE than current — leaning into "
            "small-caps degraded risk-adjusted return (the expected outcome: small-caps are "
            "more volatile / more blow-up prone)."
        )
    else:
        reason = (
            "Breadth and risk-adjusted-not-worse never coincided in one level: the levels that "
            "added small-cap breadth hurt OOS Sharpe, and the levels that held Sharpe did not "
            "add real breadth — no tilt clears both gates."
        )
    return {
        "verdict": "NO-GO", "winning_level": None,
        "winning_size_tilt_weight": 0.0, "reason": reason,
    }


# --------------------------------------------------------------------------- #
# rendering
# --------------------------------------------------------------------------- #
def _sweep_table(rows: list[dict[str, Any]]) -> list[str]:
    header = (
        "| 档位 | size_tilt | 调仓 | CAGR | Sharpe | MaxDD | OOS CAGR | OOS Sharpe "
        "| 选股数 | 中位市值(亿) | 市值分位 | 种子43占比 | 中小盘占比 |"
    )
    sep = "|" + "---|" * 13
    lines = [header, sep]
    for r in rows:
        cap = r["median_selected_cap_bn"]
        cap_bn = "—" if cap is None else f"{cap / 10:.1f}"
        pctile = "—" if r["median_cap_pctile"] is None else f"{r['median_cap_pctile']:.2f}"
        seed = "—" if r["seed43_overlap_frac"] is None else f"{r['seed43_overlap_frac']:.2f}"
        small = "—" if r["small_cap_frac"] is None else f"{r['small_cap_frac']:.2f}"
        lines.append(
            f"| {r['level']} | {r['size_tilt_weight']} | {r['rebalance_count']} | "
            f"{r['full_cagr']:.1%} | {r['full_sharpe']:.2f} | {r['full_max_drawdown']:.1%} | "
            f"{r['oos_cagr']:.1%} | {r['oos_sharpe']:.2f} | {r['selected_count']} | "
            f"{cap_bn} | {pctile} | {seed} | {small} |"
        )
    return lines


def render_markdown(
    primary: dict[str, Any], secondary: dict[str, Any] | None, window: str
) -> str:
    overall = primary["verdict"]["verdict"]
    parts = [
        "# B076 F001 — cn_attack size-tilt 对照回测（让宽池真改选股？真数字 + GO/NO-GO）",
        "",
        f"**裁定（以去偏 primary 为准）：{overall}** — {primary['verdict']['reason']}",
        "",
        "> **诚实边界：** verdict-gated（B069 NO-SWITCH 先例）——size-tilt 是策略改动，"
        "GO 才上生产；NO-GO 合法，不为『用上宽池』硬上一个更差的策略。回测用 **B070 去偏 PIT "
        "宽宇宙**（中小盘幸存者偏差最重，不得用 B075 当前 1490）。OOS 正收益部分落在 2024Q4『924』"
        "反弹窗口（B070 caveat），OOS>IS 多为窗口落位、非稳健性证据。即便 GO 也只是选股更广，"
        "**不改 cn_attack 研究态 / 不可配资定性**；中小盘更激进=更可能暴雷。",
        "",
        f"窗口 {window}；equal 权重；exit momentum_decay；"
        "真成本（印花税仅卖+佣金+滑点）；WF 70/30。",
        "",
        f"## Primary（去偏）— {primary['variant']} on B070 survivorship-free PIT 宇宙",
        f"**{primary['verdict']['verdict']}** — {primary['verdict']['reason']}",
        "",
        *_sweep_table(primary["rows"]),
        "",
        "- **中小盘广度读法**：`市值分位` 越低=选股越偏小盘（0=最小，1=最大）；`中小盘占比`=选股中"
        "市值低于宇宙中位的比例；`种子43占比`=与现状蓝筹种子重叠度。"
        "tilt 真生效 → 分位↓ + 中小盘占比↑。",
    ]
    if secondary is not None:
        parts += [
            "",
            f"## Secondary（survivor-biased，**仅方向性**不作裁定）— "
            f"{secondary['variant']} on B068 当前 top-N",
            f"**{secondary['verdict']['verdict']}** — {secondary['verdict']['reason']}",
            "",
            "> 退市名无免费 quality 基本面 → quality_momentum 无法去偏；本 cut 用 B068 幸存者宇宙，"
            "**幸存者偏差反而美化中小盘**（退市小盘输家缺席）。"
            "故此 cut 仅验证 tilt 在含 quality 时的行为，NO-GO 在此更具说服力，GO 不足为凭。",
            "",
            *_sweep_table(secondary["rows"]),
        ]
    parts += [
        "",
        "## 诚实 caveat（焊死）",
        "- **去偏天花板**（B070）：仅指数可纳入band（HS300∪ZZ500∪SZ50），无 zz1000/zz800 → 退市"
        "微小盘仍缺=残余偏差；本批 size-tilt 的『中小盘』实为指数内中小盘，非真·微盘。",
        "- **OOS 窗口**：70/30 把 2024Q4『924』反弹放进 OOS；正 OOS 含窗口顺风，非可配资证据。",
        "- **市值口径**：circ_mv 由 baostock `turn` 反推"
        "（close×volume×100/turn，未复权），月末降采样。",
        "- **research-only**：no-broker / no 真金 / 不改 cn_attack 不可配资定性（B075 同）。",
    ]
    return "\n".join(parts)


def build_payload(
    primary: dict[str, Any], secondary: dict[str, Any] | None, window: str
) -> dict[str, Any]:
    return {
        "batch": "b076_f001_size_tilt_comparison",
        "window": window,
        "headline_verdict": primary["verdict"]["verdict"],
        "primary": primary,
        "secondary": secondary,
    }


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def _seed_set() -> frozenset[str]:
    from workbench_api.data_refresh.cn_universe import CN_UNIVERSE_SEED

    return frozenset(CN_UNIVERSE_SEED)


def _load_root(root: Path, *, needs_fundamentals: bool) -> dict[str, Any]:
    os.environ["WORKBENCH_DATA_ROOT"] = str(root.resolve())
    from trade.data.cn_attack_universe import load_cn_universe_history
    from trade.data.us_quality_universe import load_fundamentals, load_prices

    prices = load_prices()
    fundamentals = load_fundamentals() if needs_fundamentals else None
    universe_history = load_cn_universe_history()
    return {"prices": prices, "fundamentals": fundamentals, "universe_history": universe_history}


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seed_set = _seed_set()
    window = f"{args.start.isoformat()}..{args.end.isoformat() if args.end else 'today'}"

    # Primary — de-biased pure_momentum on the B070 PIT universe + cn_size.csv.
    b070 = _load_root(args.b070_root, needs_fundamentals=False)
    b070_marketcap = load_marketcap(args.b070_size)
    primary_rows = run_sweep(
        FACTOR_VARIANT_PURE_MOMENTUM,
        prices=b070["prices"], marketcap=b070_marketcap, fundamentals=None,
        universe_history=b070["universe_history"], start=args.start, end=args.end,
        seed_set=seed_set,
    )
    primary = {
        "cut": "debiased_pure_momentum",
        "variant": FACTOR_VARIANT_PURE_MOMENTUM,
        "universe": "b070_survivorship_free_pit",
        "rows": primary_rows,
        "verdict": judge_size_tilt(primary_rows),
    }

    secondary: dict[str, Any] | None = None
    if args.b068_root is not None:
        b068 = _load_root(args.b068_root, needs_fundamentals=True)
        b068_marketcap = load_marketcap(
            args.b068_root / "snapshots" / "universe" / "cn_marketcap.csv"
        )
        secondary_rows = run_sweep(
            FACTOR_VARIANT_QUALITY_MOMENTUM,
            prices=b068["prices"], marketcap=b068_marketcap, fundamentals=b068["fundamentals"],
            universe_history=b068["universe_history"], start=args.start, end=args.end,
            seed_set=seed_set,
        )
        secondary = {
            "cut": "survivor_quality_momentum",
            "variant": FACTOR_VARIANT_QUALITY_MOMENTUM,
            "universe": "b068_current_top_n",
            "rows": secondary_rows,
            "verdict": judge_size_tilt(secondary_rows),
        }

    markdown = render_markdown(primary, secondary, window)
    payload = build_payload(primary, secondary, window)
    args.out_md.parent.mkdir(parents=True, exist_ok=True)
    args.out_md.write_text(markdown, encoding="utf-8")
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(markdown)
    print("\n--- payload:", args.out_json, "---")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
