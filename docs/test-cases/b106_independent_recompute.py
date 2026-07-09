"""B106 F003 — 独立验收复算（Evaluator，代 Codex）.

独立复算 B106 组合层 uplift A/B 报告的数字，用于 signoff。设计原则（守铁律 4 独立性）：

- **复用**（数据 / 策略层，非验收对象）：runner 的 sleeve-return 重构
  （momentum/risk_parity/us_quality/hk_china/defensive 各腿原生频率还原）、
  F001 已测的 `resolve_sleeve_weights` 滚动权重派生、master barbell 构造器。
- **独立自写**（本次验收对象——报告数字所依赖的"量化数学层"，用 numpy 从零实现，
  不调用 runner 的 annualized_metrics / max_drawdown / combine_fixed / combine_dynamic /
  correlation / recovery_gain / verdict_from_metrics）：
    * 固定权重 & 动态权重组合
    * 5 方案共同窗口对齐（scheme-date 交集）
    * CAGR / 年化波动 / Sharpe / MaxDD / 回本涨幅
    * Pearson 相关系数（scipy 本机无 → 自写）
    * verdict 双门槛（ΔSharpe≥0.15 且 ΔMaxDD≥3pp）

对照基准：已提交并逐字节可复现的 `data/research/b106/ab_results.json`。

用法：`.venv/bin/python docs/test-cases/b106_independent_recompute.py`
退出码 0 = 全部独立复算与报告一致（容差内）；非 0 = 有偏离（打印明细）。
本机 research-only / no-broker / 不碰真金。
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

# --- 复用：runner 的数据/策略层 + F001 权重派生（非验收对象）------------------ #
from scripts.research.b106_portfolio_uplift_ab import (
    ATTACK_SLEEVES,
    BASELINE_WEIGHTS,
    DEFENSIVE_WEIGHT,
    GLOBAL_ETF_UNIVERSE,
    RESULTS_JSON,
    RISK_PARITY_UNIVERSE,
    SLEEVE_DEFENSIVE,
    WINDOW_END,
    WINDOW_START,
    _common_dates,
    _load_fx_cny_per_usd,
    _merge_usq_into_panel,
    build_price_panel,
    cny_returns_to_usd,  # FX 换算：单独做方向正确性检验，不用于金属复算
    defensive_sleeve_returns_cny,
    hk_china_sleeve_returns,
    momentum_sleeve_returns,
    risk_parity_sleeve_returns,
    rolling_scheme_weights,
    us_quality_sleeve_returns,
    vol_target_weights,
)
from trade.portfolio.master import (
    WEIGHT_SCHEME_HRP,
    WEIGHT_SCHEME_RISK_PARITY,
    master_portfolio_parameters_with_defensive_barbell,
)

MONTHS = 12
TOL = 5e-4  # 容差：0.05pp / 0.0005 Sharpe（浮点+复算路径差异内）

_failures: list[str] = []


def _check(label: str, got: float, expected: float, tol: float = TOL) -> None:
    ok = abs(got - expected) <= tol
    flag = "✓" if ok else "✗ FAIL"
    print(f"  {flag}  {label:52s} indep={got:+.5f}  report={expected:+.5f}  Δ={got-expected:+.2e}")
    if not ok:
        _failures.append(f"{label}: indep={got:.6f} report={expected:.6f} Δ={got-expected:.2e}")


# --------------------------------------------------------------------------- #
# 独立自写：组合 + 指标数学（numpy，不调 runner）
# --------------------------------------------------------------------------- #

def indep_combine_fixed(sr, weights):
    dates = _common_dates(sr, weights.keys())
    tot = sum(weights.values())
    return {d: sum(weights[s] * sr[s][d] for s in weights) / tot for d in dates}


def indep_combine_dynamic(sr, weight_series, normalize=True):
    out = {}
    for d, w in weight_series.items():
        keys = [s for s in w if d in sr.get(s, {})]
        gross = sum(w[s] * sr[s][d] for s in keys)
        if normalize:
            tw = sum(w[s] for s in keys)
            if tw <= 0:
                continue
            out[d] = gross / tw
        else:
            out[d] = gross
    return out


def indep_metrics(port: dict[date, float]) -> dict[str, float]:
    """CAGR/ann_vol/Sharpe/MaxDD/recovery — 全部 numpy 自写，与 runner 独立。"""
    dates = sorted(port)
    r = np.array([port[d] for d in dates], dtype=float)
    n = len(r)
    # NAV（复利）
    nav = np.cumprod(1.0 + r)
    # CAGR
    years = n / MONTHS
    cagr = nav[-1] ** (1.0 / years) - 1.0 if years > 0 and nav[-1] > 0 else 0.0
    # 年化波动（样本标准差 ddof=1）
    mean = r.mean()
    std = r.std(ddof=1) if n > 1 else 0.0
    ann_vol = std * math.sqrt(MONTHS)
    sharpe = (mean / std * math.sqrt(MONTHS)) if std > 1e-12 else 0.0
    # MaxDD（独立：逐点 running-max）
    running_peak = np.maximum.accumulate(nav)
    dd = nav / running_peak - 1.0
    maxdd = float(dd.min())
    # 回本涨幅
    x = -maxdd
    recov = x / (1.0 - x) if 0.0 < x < 1.0 else (float("inf") if x >= 1.0 else 0.0)
    return {
        "n": n, "cagr": cagr, "ann_vol": ann_vol, "sharpe": sharpe,
        "max_drawdown": maxdd, "recovery_gain": recov, "final_nav": float(nav[-1]),
    }


def indep_pearson(a: dict[date, float], b: dict[date, float]) -> float:
    dates = sorted(set(a) & set(b))
    x = np.array([a[d] for d in dates], dtype=float)
    y = np.array([b[d] for d in dates], dtype=float)
    if len(x) < 3:
        return float("nan")
    xc, yc = x - x.mean(), y - y.mean()
    denom = math.sqrt((xc @ xc) * (yc @ yc))
    return float(xc @ yc / denom) if denom > 0 else float("nan")


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #

def main() -> int:
    report = json.loads(Path(RESULTS_JSON).read_text(encoding="utf-8"))
    rm = report["scheme_metrics"]

    print("=" * 78)
    print("B106 F003 独立复算（numpy 自写指标数学，不调 runner 内部函数）")
    print("=" * 78)

    # --- 复用数据层：重构 sleeve returns（USD 口径）--------------------------- #
    from trade.data.us_quality_universe import load_prices as load_usq_prices
    all_tickers = set(GLOBAL_ETF_UNIVERSE) | set(RISK_PARITY_UNIVERSE)
    all_tickers |= {"FXI", "MCHI", "KWEB", "EWH", "EEM"}
    usq_frame = load_usq_prices()
    all_tickers |= set(usq_frame["ticker"].unique())
    panel = build_price_panel(tuple(sorted(all_tickers)))
    _merge_usq_into_panel(panel, usq_frame)

    sleeve_returns = {
        "momentum": momentum_sleeve_returns(panel),
        "risk_parity": risk_parity_sleeve_returns(panel),
        "satellite_us_quality": us_quality_sleeve_returns(panel),
        "satellite_hk_china": hk_china_sleeve_returns(panel),
    }
    def_cny = defensive_sleeve_returns_cny()
    fx = _load_fx_cny_per_usd()
    def_usd_full = cny_returns_to_usd(def_cny, fx)
    def_usd = {d: r for d, r in def_usd_full.items() if WINDOW_START <= d <= WINDOW_END}
    def_cny_win = {d: r for d, r in def_cny.items() if WINDOW_START <= d <= WINDOW_END}
    sleeve_returns[SLEEVE_DEFENSIVE] = def_usd

    common = [d for d in _common_dates(sleeve_returns, sleeve_returns.keys())
              if WINDOW_START <= d <= WINDOW_END]
    sr = {s: {d: sleeve_returns[s][d] for d in common} for s in sleeve_returns}
    print(f"\nsleeve 共同窗口: {common[0]}..{common[-1]}  n={len(common)}m "
          f"(报告 methodology.window={report['methodology']['window']} "
          f"n={report['methodology']['n_months']})")

    # --- 独立组合 5 方案 ---------------------------------------------------- #
    baseline_port = indep_combine_fixed(sr, BASELINE_WEIGHTS)
    bf_params = master_portfolio_parameters_with_defensive_barbell(DEFENSIVE_WEIGHT, "fixed")
    bf_w = {s.sleeve_id: s.planning_weight for s in bf_params.sleeves}
    barbell_fixed_port = indep_combine_fixed(sr, bf_w)
    rp_w = rolling_scheme_weights(WEIGHT_SCHEME_RISK_PARITY, sr, common)
    barbell_rp_port = indep_combine_dynamic(sr, rp_w, normalize=True)
    hrp_w = rolling_scheme_weights(WEIGHT_SCHEME_HRP, sr, common)
    barbell_hrp_port = indep_combine_dynamic(sr, hrp_w, normalize=True)
    vt_w = vol_target_weights(sr, common)
    barbell_vt_port = indep_combine_dynamic(sr, vt_w, normalize=False)  # ★ 现金残差

    schemes_raw = {
        "1_baseline_fixed": baseline_port,
        "2_barbell_fixed": barbell_fixed_port,
        "3_barbell_risk_parity": barbell_rp_port,
        "4_barbell_hrp": barbell_hrp_port,
        "5_barbell_vol_target": barbell_vt_port,
    }
    # ★ 独立复现窗口对齐（5 方案共同交集）
    scheme_dates = sorted(set.intersection(*(set(p) for p in schemes_raw.values())))
    schemes = {n: {d: p[d] for d in scheme_dates} for n, p in schemes_raw.items()}
    print(f"scheme 对齐窗口: {scheme_dates[0]}..{scheme_dates[-1]}  n={len(scheme_dates)}m "
          f"(报告 scheme_window={report['methodology']['scheme_window']} "
          f"n={report['methodology']['scheme_n_months']})")
    if len(scheme_dates) != report["methodology"]["scheme_n_months"]:
        _failures.append("scheme 对齐窗口月数不一致")

    # --- 独立指标复算 vs 报告（全 5 方案）---------------------------------- #
    print("\n[1] 5 方案指标独立复算（CAGR / Sharpe / MaxDD / 回本 / NAV）")
    indep_m = {}
    for name, port in schemes.items():
        m = indep_metrics(port)
        indep_m[name] = m
        r = rm[name]
        print(f"\n  {name}  (indep n={m['n']} / report n={r['n_months']})")
        _check(f"{name}.CAGR", m["cagr"], r["cagr"])
        _check(f"{name}.ann_vol", m["ann_vol"], r["ann_vol"])
        _check(f"{name}.Sharpe", m["sharpe"], r["sharpe"])
        _check(f"{name}.MaxDD", m["max_drawdown"], r["max_drawdown"])
        _check(f"{name}.recovery_gain", m["recovery_gain"], r["recovery_gain"])
        _check(f"{name}.final_nav", m["final_nav"], r["final_nav"], tol=2e-3)

    # --- 独立 verdict 门槛复算 --------------------------------------------- #
    print("\n[2] verdict 双门槛独立复算（ΔSharpe≥0.15 且 ΔMaxDD≥3pp）")
    base = indep_m["1_baseline_fixed"]
    rep_verdict = {r["scheme"]: r for r in report["verdict"]["ranked"]}
    any_pass = False
    candidate_names = (
        "3_barbell_risk_parity", "4_barbell_hrp", "2_barbell_fixed", "5_barbell_vol_target",
    )
    for name in candidate_names:
        m = indep_m[name]
        d_sharpe = m["sharpe"] - base["sharpe"]
        d_maxdd = m["max_drawdown"] - base["max_drawdown"]
        passes = d_sharpe >= 0.15 and d_maxdd >= 0.03
        any_pass = any_pass or passes
        rv = rep_verdict[name]
        _check(f"{name}.ΔSharpe", d_sharpe, rv["delta_sharpe"])
        _check(f"{name}.ΔMaxDD", d_maxdd, rv["delta_maxdd"])
        if passes != rv["passes_gate"]:
            _failures.append(f"{name} gate 判定不一致 indep={passes} report={rv['passes_gate']}")
    decision = "GO" if any_pass else "NO-GO"
    rep_decision = report["verdict"]["decision"]
    print(f"\n  独立裁定 decision = {decision}  (报告 = {rep_decision})")
    if decision != rep_decision:
        _failures.append(f"verdict decision 不一致 indep={decision} report={rep_decision}")

    # --- 独立相关性复算（红利低波 vs 进攻腿，USD & CNY 原生）--------------- #
    print("\n[3] 相关性独立复算（Pearson 自写）")
    rep_corr_usd = report["correlations_defensive_vs_attack"]
    rep_corr_cny = report["correlations_defensive_cny_native_vs_attack"]
    for s in ATTACK_SLEEVES:
        c_usd = indep_pearson(sr[SLEEVE_DEFENSIVE], sr[s])
        _check(f"corr USD  def~{s}", c_usd, rep_corr_usd[f"{SLEEVE_DEFENSIVE}~{s}"])
        c_cny = indep_pearson(def_cny_win, sr[s])
        _check(f"corr CNY  def~{s}", c_cny, rep_corr_cny[f"{SLEEVE_DEFENSIVE}_cny~{s}"])
    # 全部弱正非负（分散前提不成立）
    all_usd = [indep_pearson(sr[SLEEVE_DEFENSIVE], sr[s]) for s in ATTACK_SLEEVES]
    print(f"\n  USD 相关区间 [{min(all_usd):+.3f}, {max(all_usd):+.3f}] — "
          f"{'全非负 ✓ (弱正, 分散前提不成立)' if min(all_usd) >= 0 else '★出现负值!'}")
    if min(all_usd) < 0:
        _failures.append("USD 相关性出现负值，与报告'弱正非负'矛盾")

    # --- 防守腿 CNY-native vs USD-converted 口径 + FX 方向 ------------------ #
    print("\n[4] 防守腿币种口径 + FX 方向正确性")
    dc = report["defensive_currency_口径"]
    m_cny = indep_metrics(def_cny_win)
    m_usd = indep_metrics(sr[SLEEVE_DEFENSIVE])
    _check("def CNY-native.Sharpe", m_cny["sharpe"], dc["cny_native"]["sharpe"])
    _check("def CNY-native.CAGR", m_cny["cagr"], dc["cny_native"]["cagr"])
    _check("def CNY-native.MaxDD", m_cny["max_drawdown"], dc["cny_native"]["max_drawdown"])
    _check("def USD-converted.Sharpe", m_usd["sharpe"], dc["usd_converted"]["sharpe"])
    _check("def USD-converted.CAGR", m_usd["cagr"], dc["usd_converted"]["cagr"])
    _check("def USD-converted.MaxDD", m_usd["max_drawdown"], dc["usd_converted"]["max_drawdown"])
    # FX 拖累方向：USD 换算后 Sharpe/CAGR 应低于 CNY 原生（人民币贬值伤 USD 投资者）
    drag_ok = m_usd["sharpe"] < m_cny["sharpe"] and m_usd["cagr"] < m_cny["cagr"]
    print(f"\n  FX 拖累方向: USD Sharpe {m_usd['sharpe']:.3f} < CNY {m_cny['sharpe']:.3f} 且 "
          f"USD CAGR {m_usd['cagr']*100:.2f}% < CNY {m_cny['cagr']*100:.2f}%  "
          f"→ {'✓ 换算削收益(方向正确)' if drag_ok else '✗ 方向异常'}")
    if not drag_ok:
        _failures.append("FX 换算方向异常：USD 换算未削减防守腿收益")
    # FX 序列方向：2015 ~6.19 → 2024 ~7.17（CNY per USD 上升=人民币贬值）
    fx_2015 = float(fx[fx.index <= "2015-12-31"].iloc[-1])
    fx_2024 = float(fx[fx.index <= "2024-12-31"].iloc[-1])
    print(f"  FX(CNY per USD): 2015≈{fx_2015:.3f} → 2024≈{fx_2024:.3f}  "
          f"({'✓ 上升=人民币贬值' if fx_2024 > fx_2015 else '✗'})")
    if fx_2024 <= fx_2015:
        _failures.append("FX 序列方向异常")
    # cny_returns_to_usd 公式方向（合成检验）：rate 升 → USD 投资者亏
    import pandas as pd
    fx_syn = pd.Series([6.0, 6.6], index=pd.to_datetime(["2020-01-31", "2020-02-29"]))
    syn = cny_returns_to_usd({date(2020, 1, 31): 0.0, date(2020, 2, 29): 0.10}, fx_syn)
    # (1.10)*(6.0/6.6)-1 = 0.0：+10% CNY 恰被 10% 贬值抵消
    _check("FX公式 (1+0.10)*(6.0/6.6)-1", syn[date(2020, 2, 29)], 0.0, tol=1e-9)

    # --- 回撤复利算术核对 -------------------------------------------------- #
    print("\n[5] 回撤复利算术核对 (recovery = |dd|/(1-|dd|))")
    for name in ("1_baseline_fixed", "3_barbell_risk_parity"):
        dd = indep_m[name]["max_drawdown"]
        expected_recov = (-dd) / (1.0 + dd)
        _check(f"{name} 回本涨幅", indep_m[name]["recovery_gain"], expected_recov, tol=1e-9)

    # --- 结论 -------------------------------------------------------------- #
    print("\n" + "=" * 78)
    if _failures:
        print(f"独立复算 FAIL — {len(_failures)} 项偏离:")
        for f in _failures:
            print(f"  ✗ {f}")
        return 1
    print("独立复算全 PASS — 5 方案指标 / verdict / 相关性 / 口径 / FX 方向 / 回撤复利")
    print("均与报告一致（容差内），且 numpy 自写数学独立于 runner。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
