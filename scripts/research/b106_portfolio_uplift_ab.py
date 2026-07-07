"""B106 F002 — Master 组合层 uplift A/B: 防守腿杠铃 + 权重方案对照 + verdict.

Runs a **sleeve-return-level** portfolio A/B comparing the production Master baseline
(4-sleeve fixed 40/30/20/10, NO defensive leg) against four barbell variants that add
the B082-validated cn_dividend_lowvol defensive sleeve at 20% and re-weight the sleeves:

  ① baseline        — 4 attack sleeves, fixed 40/30/20/10 (reproduces the production default)
  ② barbell+fixed   — +cn_dividend_lowvol 20%, attack scaled ×0.8 (32/24/16/8), fixed
  ③ barbell+risk_parity — 5 sleeves inverse-volatility weighted (rolling, no look-ahead)
  ④ barbell+hrp     — 5 sleeves Hierarchical Risk Parity weighted (rolling)
  ⑤ barbell+vol_target  — fixed barbell weights, exposure scaled to an 8% vol target

★★ Cross-market 口径 honesty (本批最大方法学陷阱)
The four attack sleeves are USD-denominated (US/global ETFs, tiingo adj_close). The
defensive sleeve is CNY-denominated (H20269 全收益指数 2005+). A naive mixed-currency
portfolio Sharpe would MISLEAD. The PRIMARY 口径 here is **USD-unified**: the CNY
defensive returns are converted to a USD investor's realised returns via the USD/CNY
FX series (CNY per USD). A secondary **CNY-native** view of the defensive leg is also
reported so the currency drag is explicit and separable.

★ Why not run the production Master engine over real data?
``run_master_portfolio_quarterly_backtest`` feeds ONE ``records`` tuple to every sleeve,
but the sleeves need incompatible bar cadences: global_etf_momentum measures its 3/6/9
"periods" in *available observations* (designed for month-end bars), while
risk_parity_vol_target needs 120 *daily* observations for its volatility estimate. The
engine is fixture-calibrated and cannot honestly run both over one raw real-data panel.
So each sleeve is reconstructed at its own native cadence and combined at the monthly
sleeve-return level — an internally-consistent A/B that isolates the barbell effect.

Output: ``data/research/b106/ab_results.json`` (all numbers, reproducible) + a human
summary to stderr. ``docs/test-reports/B106-portfolio-uplift-ab.md`` lifts these verbatim.

Usage: .venv/bin/python scripts/research/b106_portfolio_uplift_ab.py
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from trade.data.loader import PriceBar
from trade.portfolio.master import (
    WEIGHT_SCHEME_HRP,
    WEIGHT_SCHEME_RISK_PARITY,
    master_portfolio_parameters_with_defensive_barbell,
    resolve_sleeve_weights,
)
from trade.strategies.global_etf_momentum import (
    MomentumParameters,
    generate_momentum_signal,
)

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

TIINGO_DIR = Path("data/snapshots/prices/tiingo")
B082_DIR = Path("data/research/b082")
FX_CSV = Path("data/research/b090_hk/fx_daily.csv")
OUT_DIR = Path("data/research/b106")
RESULTS_JSON = OUT_DIR / "ab_results.json"

MONTHS_PER_YEAR = 12
# Friction per unit turnover (10 bps commission+slippage on the USD ETF book), applied
# to the sleeve-level turnover at each monthly rebalance. Matches the order of magnitude
# of the Master engine's cost_bps+slippage_bps default.
FRICTION_RATE = 10.0 / 10_000.0

# Global-ETF momentum universe (defensive = AGG). A documented research universe; the
# defensive-leg verdict is robust to the exact attack universe (relative comparison).
GLOBAL_ETF_UNIVERSE: tuple[str, ...] = (
    "SPY", "QQQ", "EFA", "EEM", "IWM", "TLT", "IEF", "GLD", "AGG",
)
MOMENTUM_DEFENSIVE = "AGG"

# risk_parity_vol_target production universe.
RISK_PARITY_UNIVERSE: tuple[str, ...] = ("SPY", "VEA", "AGG", "GLD", "SGOV")

# Sleeve ids as they appear in the Master barbell config (see trade/portfolio/master.py).
SLEEVE_MOMENTUM = "momentum"
SLEEVE_RISK_PARITY = "risk_parity"
SLEEVE_US_QUALITY = "satellite_us_quality"
SLEEVE_HK_CHINA = "satellite_hk_china"
SLEEVE_DEFENSIVE = "cn_dividend_lowvol"
ATTACK_SLEEVES: tuple[str, ...] = (
    SLEEVE_MOMENTUM, SLEEVE_RISK_PARITY, SLEEVE_US_QUALITY, SLEEVE_HK_CHINA,
)
# Baseline fixed weights (production default 40/30/20/10).
BASELINE_WEIGHTS: dict[str, float] = {
    SLEEVE_MOMENTUM: 0.40,
    SLEEVE_RISK_PARITY: 0.30,
    SLEEVE_US_QUALITY: 0.20,
    SLEEVE_HK_CHINA: 0.10,
}
DEFENSIVE_WEIGHT = 0.20

# A/B window: bounded by tiingo start (2014-01) + momentum/vol warmup and tiingo end.
WINDOW_START = date(2015, 1, 1)
WINDOW_END = date(2026, 5, 31)

# Rolling look-back (months) for the risk-aware schemes' weight derivation + vol target.
ROLLING_LOOKBACK_M = 12
ROLLING_MIN_M = 6
VOL_TARGET_ANNUAL = 0.08

# Drawdown-window comparison (matches B082 defensive-sleeve验收 windows).
WINDOW_2022 = (date(2022, 1, 1), date(2022, 12, 31))
WINDOW_2024_FEB = (date(2024, 1, 1), date(2024, 2, 29))

# ---- verdict-gating thresholds (pre-registered, honest) ------------------- #
# A barbell scheme is "显著优于基线" only if it MATERIALLY improves risk-adjusted return
# AND drawdown. Marginal wins → NO-GO 保持现状 (B069/B076 先例).
SHARPE_UPLIFT_GATE = 0.15   # Δannualised Sharpe vs baseline
MAXDD_UPLIFT_GATE = 0.03    # MaxDD must improve by ≥ 3 pp (less negative)


# --------------------------------------------------------------------------- #
# Pure helpers (unit-tested)
# --------------------------------------------------------------------------- #

def annualized_metrics(
    returns: list[float], periods_per_year: int = MONTHS_PER_YEAR
) -> dict[str, float]:
    """CAGR, annualised volatility and Sharpe (rf=0) from a periodic return series."""

    if not returns:
        return {"cagr": 0.0, "ann_vol": 0.0, "sharpe": 0.0, "n": 0}
    nav = 1.0
    for r in returns:
        nav *= 1.0 + r
    years = len(returns) / periods_per_year
    cagr = nav ** (1.0 / years) - 1.0 if years > 0 and nav > 0 else 0.0
    mean = sum(returns) / len(returns)
    if len(returns) > 1:
        var = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
        std = math.sqrt(var)
    else:
        std = 0.0
    ann_vol = std * math.sqrt(periods_per_year)
    # Guard against float-noise std on (near-)constant series → avoid a blown-up Sharpe.
    sharpe = (mean / std * math.sqrt(periods_per_year)) if std > 1e-12 else 0.0
    return {"cagr": cagr, "ann_vol": ann_vol, "sharpe": sharpe, "n": len(returns)}


def nav_curve(returns: list[float]) -> list[float]:
    """Cumulative NAV starting at 1.0 (one point per return)."""

    nav = 1.0
    out: list[float] = []
    for r in returns:
        nav *= 1.0 + r
        out.append(nav)
    return out


def max_drawdown(nav: list[float]) -> float:
    """Maximum peak-to-trough drawdown of a NAV series (<= 0)."""

    if not nav:
        return 0.0
    peak = nav[0]
    worst = 0.0
    for value in nav:
        peak = max(peak, value)
        if peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def recovery_gain(drawdown: float) -> float:
    """Gain required to recover a drawdown: −X% → +Y% where Y = X/(1−X)."""

    if drawdown >= 0:
        return 0.0
    x = -drawdown
    if x >= 1.0:
        return float("inf")
    return x / (1.0 - x)


def cny_returns_to_usd(
    cny_returns: dict[date, float], fx_cny_per_usd: pd.Series
) -> dict[date, float]:
    """Convert a CNY-native return series to a USD investor's realised returns.

    A USD investor's holding value is ``CNY_value / (CNY per USD)``. Over a period the
    USD return is ``(1+r_cny) * fx_prev/fx_now - 1``. ``fx_cny_per_usd`` is a daily
    series of CNY-per-USD; each period boundary uses the last quote on/before that date.
    """

    dates = sorted(cny_returns)
    out: dict[date, float] = {}
    prev_date: date | None = None
    for d in dates:
        if prev_date is None:
            prev_date = d
            continue
        fx_prev = _fx_asof(fx_cny_per_usd, prev_date)
        fx_now = _fx_asof(fx_cny_per_usd, d)
        if fx_prev is None or fx_now is None or fx_now <= 0:
            out[d] = cny_returns[d]  # no FX quote → fall back to native (documented)
        else:
            out[d] = (1.0 + cny_returns[d]) * (fx_prev / fx_now) - 1.0
        prev_date = d
    return out


def _fx_asof(fx: pd.Series, d: date) -> float | None:
    sub = fx[fx.index <= pd.Timestamp(d)]
    if sub.empty:
        return None
    return float(sub.iloc[-1])


def combine_fixed(
    sleeve_returns: dict[str, dict[date, float]], weights: dict[str, float]
) -> dict[date, float]:
    """Fixed-weight, monthly-rebalanced portfolio returns over the common date grid."""

    dates = _common_dates(sleeve_returns, weights.keys())
    total_w = sum(weights[s] for s in weights)
    out: dict[date, float] = {}
    for d in dates:
        r = sum(weights[s] * sleeve_returns[s][d] for s in weights)
        out[d] = r / total_w if total_w else 0.0
    return out


def combine_dynamic(
    sleeve_returns: dict[str, dict[date, float]],
    weight_series: dict[date, dict[str, float]],
    normalize: bool = True,
) -> dict[date, float]:
    """Portfolio returns where per-date sleeve weights are supplied (rolling schemes).

    ``normalize=True`` (risk_parity/hrp: weights already sum to 1, so this is a no-op
    but guards against float drift). ``normalize=False`` (vol_target: weights sum to
    < 1 by design and the residual sits in CASH earning ~0 — normalising would cancel
    the vol-target scaling, which is exactly the bug this flag avoids)."""

    out: dict[date, float] = {}
    for d, weights in weight_series.items():
        keys = [s for s in weights if d in sleeve_returns.get(s, {})]
        gross = sum(weights[s] * sleeve_returns[s][d] for s in keys)
        if normalize:
            total_w = sum(weights[s] for s in keys)
            if total_w <= 0:
                continue
            out[d] = gross / total_w
        else:
            out[d] = gross  # residual (1 - Σw) held in cash at ~0% real return
    return out


def _common_dates(sleeve_returns: dict[str, dict[date, float]], sleeves: Any) -> list[date]:
    sets = [set(sleeve_returns[s]) for s in sleeves if s in sleeve_returns]
    if not sets:
        return []
    common = set.intersection(*sets)
    return sorted(common)


def correlation(a: dict[date, float], b: dict[date, float]) -> float:
    """Pearson correlation over the two series' common dates."""

    dates = sorted(set(a) & set(b))
    n = len(dates)
    if n < 3:
        return float("nan")
    xs = [a[d] for d in dates]
    ys = [b[d] for d in dates]
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx <= 0 or vy <= 0:
        return float("nan")
    return cov / math.sqrt(vx * vy)


def window_return_and_dd(
    port_returns: dict[date, float], start: date, end: date
) -> dict[str, float]:
    """Cumulative return + max drawdown of a portfolio return series inside a window."""

    dates = [d for d in sorted(port_returns) if start <= d <= end]
    if len(dates) < 2:
        return {"return": float("nan"), "max_drawdown": float("nan")}
    rets = [port_returns[d] for d in dates]
    nav = nav_curve(rets)
    return {"return": nav[-1] - 1.0, "max_drawdown": max_drawdown(nav)}


def verdict_from_metrics(
    baseline: dict[str, float], candidates: dict[str, dict[str, float]]
) -> dict[str, Any]:
    """Gate: a candidate GOes only if ΔSharpe ≥ gate AND MaxDD improves ≥ gate."""

    ranked: list[dict[str, Any]] = []
    for name, m in candidates.items():
        d_sharpe = m["sharpe"] - baseline["sharpe"]
        d_maxdd = m["max_drawdown"] - baseline["max_drawdown"]  # >0 means less-negative = better
        passes = d_sharpe >= SHARPE_UPLIFT_GATE and d_maxdd >= MAXDD_UPLIFT_GATE
        ranked.append({
            "scheme": name,
            "delta_sharpe": d_sharpe,
            "delta_maxdd": d_maxdd,
            "passes_gate": passes,
        })
    ranked.sort(key=lambda x: x["delta_sharpe"], reverse=True)
    winners = [r for r in ranked if r["passes_gate"]]
    if winners:
        best = winners[0]
        decision = "GO"
        recommendation = (
            f"改默认 → {best['scheme']} (ΔSharpe {best['delta_sharpe']:+.3f}, "
            f"ΔMaxDD {best['delta_maxdd']*100:+.1f}pp)"
        )
    else:
        decision = "NO-GO"
        recommendation = (
            "保持现状 (default 4-sleeve fixed)。无方案在 ΔSharpe≥"
            f"{SHARPE_UPLIFT_GATE} 且 ΔMaxDD≥{MAXDD_UPLIFT_GATE*100:.0f}pp 双门槛下显著优于基线。"
        )
    return {
        "decision": decision,
        "recommendation": recommendation,
        "gates": {"sharpe_uplift": SHARPE_UPLIFT_GATE, "maxdd_uplift": MAXDD_UPLIFT_GATE},
        "ranked": ranked,
    }


# --------------------------------------------------------------------------- #
# Data loading + sleeve reconstruction
# --------------------------------------------------------------------------- #

def _load_tiingo_adjclose(ticker: str) -> pd.Series:
    matches = sorted(TIINGO_DIR.glob(f"{ticker}-*.csv"))
    if not matches:
        raise FileNotFoundError(f"no tiingo CSV for {ticker}")
    frame = pd.read_csv(matches[0], parse_dates=["date"])
    return frame.set_index("date")["adj_close"].astype(float).sort_index()


def _month_end_index(series: pd.Series) -> pd.Series:
    """Resample a daily series to the last available observation per calendar month."""

    return series.groupby([series.index.year, series.index.month]).tail(1)


@dataclass(frozen=True)
class PricePanel:
    """Month-end adj_close panel + daily records for the sleeves that need them."""

    monthly: dict[str, dict[date, float]]  # ticker -> {month_end_date: adj_close}
    month_ends: list[date]


def build_price_panel(tickers: tuple[str, ...]) -> PricePanel:
    monthly: dict[str, dict[date, float]] = {}
    all_month_ends: set[date] = set()
    for t in tickers:
        try:
            daily = _load_tiingo_adjclose(t)
        except FileNotFoundError:
            continue
        me = _month_end_index(daily)
        col = {ts.date(): float(v) for ts, v in me.items()}
        monthly[t] = col
        all_month_ends.update(col)
    month_ends = sorted(d for d in all_month_ends if WINDOW_START <= d <= WINDOW_END)
    return PricePanel(monthly=monthly, month_ends=month_ends)


def _monthly_pricebars(panel: PricePanel, universe: tuple[str, ...]) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for t in universe:
        col = panel.monthly.get(t, {})
        for d, adj in col.items():
            bars.append(PriceBar(
                date=d, symbol=t, open=adj, close=adj, adjusted_close=adj, volume=0,
            ))
    return bars


def _realized_returns_from_weights(
    weights_by_date: dict[date, dict[str, float]], panel: PricePanel
) -> dict[date, float]:
    """Given target weights set at month-end t, compute the realised return over
    [t, t+1] valued with month-end adj_close, net of turnover friction. The realised
    return is stamped on t+1 (the month it is earned)."""

    signal_dates = sorted(weights_by_date)
    out: dict[date, float] = {}
    prev_weights: dict[str, float] = {}
    for i, t in enumerate(signal_dates):
        if i + 1 >= len(signal_dates):
            break
        t_next = signal_dates[i + 1]
        weights = weights_by_date[t]
        gross = 0.0
        for sym, w in weights.items():
            p0 = panel.monthly.get(sym, {}).get(t)
            p1 = panel.monthly.get(sym, {}).get(t_next)
            if p0 is None or p1 is None or p0 <= 0:
                continue  # asset not priced this month → contributes 0 (documented)
            gross += w * (p1 / p0 - 1.0)
        turnover = sum(
            abs(weights.get(s, 0.0) - prev_weights.get(s, 0.0))
            for s in set(weights) | set(prev_weights)
        )
        out[t_next] = gross - turnover * FRICTION_RATE
        prev_weights = weights
    return out


def momentum_sleeve_returns(panel: PricePanel) -> dict[date, float]:
    bars = tuple(_monthly_pricebars(panel, GLOBAL_ETF_UNIVERSE))
    params = MomentumParameters(defensive_asset=MOMENTUM_DEFENSIVE)
    weights_by_date: dict[date, dict[str, float]] = {}
    for t in panel.month_ends:
        hist = tuple(b for b in bars if b.date <= t)
        # need >= max period + 1 monthly obs per symbol for the 9-period window
        n_obs = len({b.date for b in hist})
        if n_obs < 11:
            continue
        try:
            sig = generate_momentum_signal(hist, params, t)
        except Exception:  # noqa: BLE001 — insufficient/edge data → skip this month
            continue
        weights_by_date[t] = dict(sig.target_weights)
    return _realized_returns_from_weights(weights_by_date, panel)


def risk_parity_sleeve_returns(panel: PricePanel) -> dict[date, float]:
    """Inverse-volatility weights over the risk_parity universe, computed on the
    month-end panel (trailing 12m vol) — a faithful monthly proxy for the daily
    120-obs risk_parity_vol_target sleeve. Reuses the tested resolve_sleeve_weights
    primitive indirectly via inverse-vol; here computed inline on monthly returns."""

    # Build monthly returns per risk_parity asset.
    asset_rets: dict[str, dict[date, float]] = {}
    for ticker in RISK_PARITY_UNIVERSE:
        col = panel.monthly.get(ticker, {})
        dates = sorted(col)
        rets: dict[date, float] = {}
        for i in range(1, len(dates)):
            p0, p1 = col[dates[i - 1]], col[dates[i]]
            if p0 > 0:
                rets[dates[i]] = p1 / p0 - 1.0
        asset_rets[ticker] = rets
    weights_by_date: dict[date, dict[str, float]] = {}
    for t in panel.month_ends:
        trailing: dict[str, list[float]] = {}
        for asset, rets in asset_rets.items():
            window = [rets[d] for d in sorted(rets) if d <= t][-ROLLING_LOOKBACK_M:]
            if len(window) >= ROLLING_MIN_M:
                trailing[asset] = window
        if len(trailing) < 2:
            continue
        inv = {a: (1.0 / _stdev(w)) if _stdev(w) > 0 else 0.0 for a, w in trailing.items()}
        tot = sum(inv.values())
        if tot <= 0:
            continue
        weights_by_date[t] = {a: v / tot for a, v in inv.items()}
    return _realized_returns_from_weights(weights_by_date, panel)


def _stdev(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return math.sqrt(sum((v - mean) ** 2 for v in values) / (n - 1))


def us_quality_sleeve_returns(panel: PricePanel) -> dict[date, float]:
    from trade.strategies.us_quality_momentum.parameters import UsQualityMomentumParameters
    from trade.strategies.us_quality_momentum.signal import generate_signal

    params = UsQualityMomentumParameters()
    weights_by_date: dict[date, dict[str, float]] = {}
    for t in panel.month_ends:
        try:
            sig = generate_signal(params, t)
            w = sig.weights_dict()
        except Exception:  # noqa: BLE001
            continue
        if w:
            weights_by_date[t] = dict(w)
    return _realized_returns_from_weights(weights_by_date, panel)


def hk_china_sleeve_returns(panel: PricePanel) -> dict[date, float]:
    from trade.strategies.hk_china_momentum.parameters import HkChinaMomentumParameters
    from trade.strategies.hk_china_momentum.signal import generate_signal

    params = HkChinaMomentumParameters()
    weights_by_date: dict[date, dict[str, float]] = {}
    for t in panel.month_ends:
        try:
            sig = generate_signal(params, t)
            w = sig.weights_dict()
        except Exception:  # noqa: BLE001
            continue
        if w:
            weights_by_date[t] = dict(w)
    return _realized_returns_from_weights(weights_by_date, panel)


def defensive_sleeve_returns_cny() -> dict[date, float]:
    """CNY-native monthly returns of the cn_dividend_lowvol STRATEGY (H20269 TR 口径)."""

    from trade.backtest.cn_dividend_lowvol.engine import simulate_single_asset
    from trade.strategies.cn_dividend_lowvol.parameters import CnDividendLowvolParameters
    from trade.strategies.cn_dividend_lowvol.signal import (
        compute_spread,
        month_end_target_weights,
        reconstruct_dividend_yield,
    )

    params = CnDividendLowvolParameters()
    tr = _load_b082("index_h20269", "close")
    pr = _load_b082("index_h30269", "close")
    y10 = _load_b082("cn_10y_yield", "yield")
    divy = reconstruct_dividend_yield(tr, pr, params.dividend_yield_lookback_days)
    spread = compute_spread(divy, y10)
    targets = month_end_target_weights(spread, params)
    result = simulate_single_asset(tr, targets, cost_model=None)
    monthly_equity = _month_end_index(result.equity)
    dates = [ts.date() for ts in monthly_equity.index]
    vals = [float(v) for v in monthly_equity.to_numpy()]
    out: dict[date, float] = {}
    for i in range(1, len(dates)):
        if vals[i - 1] > 0:
            out[dates[i]] = vals[i] / vals[i - 1] - 1.0
    return out


def _load_b082(name: str, col: str) -> pd.Series:
    frame = pd.read_csv(B082_DIR / f"{name}.csv", parse_dates=["date"])
    return frame.set_index("date")[col].astype(float).sort_index()


def _load_fx_cny_per_usd() -> pd.Series:
    fx = pd.read_csv(FX_CSV, parse_dates=["date"])
    fx = fx[fx["currency"] == "CNY"].set_index("date")["rate"].astype(float).sort_index()
    return fx


# --------------------------------------------------------------------------- #
# Rolling risk-aware sleeve weights (schemes ③ ④)
# --------------------------------------------------------------------------- #

def rolling_scheme_weights(
    scheme: str,
    sleeve_returns: dict[str, dict[date, float]],
    grid: list[date],
) -> dict[date, dict[str, float]]:
    """Per-date sleeve weights via resolve_sleeve_weights over TRAILING returns only
    (no look-ahead). Reuses the tested trade.portfolio.master primitive."""

    params = master_portfolio_parameters_with_defensive_barbell(DEFENSIVE_WEIGHT, scheme)
    sleeves = params.sleeves
    sleeve_ids = [s.sleeve_id for s in sleeves]
    weight_series: dict[date, dict[str, float]] = {}
    for t in grid:
        trailing: dict[str, list[float]] = {}
        ok = True
        for sid in sleeve_ids:
            rets = sleeve_returns.get(sid, {})
            window = [rets[d] for d in sorted(rets) if d < t][-ROLLING_LOOKBACK_M:]
            if len(window) < ROLLING_MIN_M:
                ok = False
                break
            trailing[sid] = window
        if not ok:
            continue
        try:
            weight_series[t] = resolve_sleeve_weights(scheme, sleeves, trailing)
        except Exception:  # noqa: BLE001 — degenerate window (flat sleeve) → skip month
            continue
    return weight_series


def vol_target_weights(
    sleeve_returns: dict[str, dict[date, float]], grid: list[date]
) -> dict[date, dict[str, float]]:
    """Fixed barbell weights scaled so trailing portfolio vol hits VOL_TARGET_ANNUAL;
    residual exposure sits in cash (contributes ~0). Overlay on the fixed barbell."""

    params = master_portfolio_parameters_with_defensive_barbell(DEFENSIVE_WEIGHT, "fixed")
    base = {s.sleeve_id: s.planning_weight for s in params.sleeves}
    # Pre-compute the fixed-barbell portfolio return each month for the vol estimate.
    fixed_port = combine_fixed(sleeve_returns, base)
    weight_series: dict[date, dict[str, float]] = {}
    for t in grid:
        window = [fixed_port[d] for d in sorted(fixed_port) if d < t][-ROLLING_LOOKBACK_M:]
        if len(window) < ROLLING_MIN_M:
            continue
        realized_vol = _stdev(window) * math.sqrt(MONTHS_PER_YEAR)
        scale = 1.0 if realized_vol <= 0 else min(1.0, VOL_TARGET_ANNUAL / realized_vol)
        weight_series[t] = {sid: w * scale for sid, w in base.items()}
    return weight_series


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def _metrics_block(port: dict[date, float]) -> dict[str, Any]:
    dates = sorted(port)
    rets = [port[d] for d in dates]
    nav = nav_curve(rets)
    m = annualized_metrics(rets)
    mdd = max_drawdown(nav)
    return {
        "window": f"{dates[0]}..{dates[-1]}" if dates else "empty",
        "n_months": len(rets),
        "cagr": m["cagr"],
        "ann_vol": m["ann_vol"],
        "sharpe": m["sharpe"],
        "max_drawdown": mdd,
        "recovery_gain": recovery_gain(mdd),
        "final_nav": nav[-1] if nav else 1.0,
    }


def run() -> dict[str, Any]:
    # --- price panel (union of every sleeve's tickers) --------------------- #
    from trade.data.us_quality_universe import load_prices as load_usq_prices

    all_tickers = set(GLOBAL_ETF_UNIVERSE) | set(RISK_PARITY_UNIVERSE)
    all_tickers |= {"FXI", "MCHI", "KWEB", "EWH", "EEM"}  # hk_china candidates
    usq_frame = load_usq_prices()
    all_tickers |= set(usq_frame["ticker"].unique())
    panel = build_price_panel(tuple(sorted(all_tickers)))

    # us_quality tickers may only be in the usq frame → merge those columns in.
    _merge_usq_into_panel(panel, usq_frame)

    # --- sleeve return series (USD) ---------------------------------------- #
    sleeve_returns: dict[str, dict[date, float]] = {
        SLEEVE_MOMENTUM: momentum_sleeve_returns(panel),
        SLEEVE_RISK_PARITY: risk_parity_sleeve_returns(panel),
        SLEEVE_US_QUALITY: us_quality_sleeve_returns(panel),
        SLEEVE_HK_CHINA: hk_china_sleeve_returns(panel),
    }

    # --- defensive sleeve: CNY-native → USD -------------------------------- #
    def_cny = defensive_sleeve_returns_cny()
    fx = _load_fx_cny_per_usd()
    def_usd_full = cny_returns_to_usd(def_cny, fx)
    def_usd = {d: r for d, r in def_usd_full.items() if WINDOW_START <= d <= WINDOW_END}
    def_cny_win = {d: r for d, r in def_cny.items() if WINDOW_START <= d <= WINDOW_END}
    sleeve_returns[SLEEVE_DEFENSIVE] = def_usd

    # --- restrict every sleeve to the common date grid --------------------- #
    common = _common_dates(sleeve_returns, sleeve_returns.keys())
    common = [d for d in common if WINDOW_START <= d <= WINDOW_END]
    sr = {s: {d: sleeve_returns[s][d] for d in common} for s in sleeve_returns}

    # --- 5 schemes --------------------------------------------------------- #
    baseline_port = combine_fixed(sr, BASELINE_WEIGHTS)

    barbell_fixed_params = master_portfolio_parameters_with_defensive_barbell(
        DEFENSIVE_WEIGHT, "fixed"
    )
    barbell_fixed_w = {s.sleeve_id: s.planning_weight for s in barbell_fixed_params.sleeves}
    barbell_fixed_port = combine_fixed(sr, barbell_fixed_w)

    rp_weights = rolling_scheme_weights(WEIGHT_SCHEME_RISK_PARITY, sr, common)
    barbell_rp_port = combine_dynamic(sr, rp_weights)

    hrp_weights = rolling_scheme_weights(WEIGHT_SCHEME_HRP, sr, common)
    barbell_hrp_port = combine_dynamic(sr, hrp_weights)

    vt_weights = vol_target_weights(sr, common)
    barbell_vt_port = combine_dynamic(sr, vt_weights, normalize=False)

    schemes_raw = {
        "1_baseline_fixed": baseline_port,
        "2_barbell_fixed": barbell_fixed_port,
        "3_barbell_risk_parity": barbell_rp_port,
        "4_barbell_hrp": barbell_hrp_port,
        "5_barbell_vol_target": barbell_vt_port,
    }
    # ★ Fair comparison: the rolling schemes (③④⑤) warm up ~6m later. Align EVERY
    # scheme to the common date intersection so metrics/verdict span one window.
    scheme_dates = sorted(set.intersection(*(set(p) for p in schemes_raw.values())))
    schemes = {
        name: {d: p[d] for d in scheme_dates} for name, p in schemes_raw.items()
    }
    scheme_metrics = {name: _metrics_block(p) for name, p in schemes.items()}

    # --- correlations (sleeve returns, USD) -------------------------------- #
    corr = {}
    for s in ATTACK_SLEEVES:
        corr[f"{SLEEVE_DEFENSIVE}~{s}"] = correlation(sr[SLEEVE_DEFENSIVE], sr[s])
    corr_matrix = {
        a: {b: correlation(sr[a], sr[b]) for b in sr} for a in sr
    }
    # ★ The B082-cited negative correlation was 红利低波 vs A-SHARE momentum (both CNY).
    # This Master book holds US/global momentum. Report the CNY-native defensive leg's
    # correlation with the (USD) attack sleeves to show the diversification premise does
    # NOT transfer — neither market nor currency matches.
    corr_cny_native = {
        f"{SLEEVE_DEFENSIVE}_cny~{s}": correlation(def_cny_win, sr[s])
        for s in ATTACK_SLEEVES
    }

    # --- drawdown windows (2022 / 2024-02) --------------------------------- #
    dd_windows = {}
    for name, port in schemes.items():
        dd_windows[name] = {
            "2022": window_return_and_dd(port, *WINDOW_2022),
            "2024_jan_feb": window_return_and_dd(port, *WINDOW_2024_FEB),
        }

    # --- verdict ----------------------------------------------------------- #
    baseline_m = scheme_metrics["1_baseline_fixed"]
    candidate_m = {k: v for k, v in scheme_metrics.items() if k != "1_baseline_fixed"}
    verdict = verdict_from_metrics(baseline_m, candidate_m)

    # --- defensive-leg currency 口径 (CNY-native vs USD-converted) --------- #
    def_native_m = _metrics_block(def_cny_win)
    def_usd_m = _metrics_block(sr[SLEEVE_DEFENSIVE])

    return {
        "methodology": {
            "note": "sleeve-return-level monthly A/B; USD-unified primary 口径; "
                    "CNY defensive leg FX-converted (CNY per USD).",
            "window": f"{common[0]}..{common[-1]}" if common else "empty",
            "n_months": len(common),
            "scheme_window": f"{scheme_dates[0]}..{scheme_dates[-1]}" if scheme_dates else "empty",
            "scheme_n_months": len(scheme_dates),
            "friction_rate_bps": FRICTION_RATE * 10_000,
            "rolling_lookback_m": ROLLING_LOOKBACK_M,
            "vol_target_annual": VOL_TARGET_ANNUAL,
            "momentum_universe": list(GLOBAL_ETF_UNIVERSE),
            "risk_parity_universe": list(RISK_PARITY_UNIVERSE),
        },
        "scheme_metrics": scheme_metrics,
        "verdict": verdict,
        "correlations_defensive_vs_attack": corr,
        "correlations_defensive_cny_native_vs_attack": corr_cny_native,
        "correlation_matrix": corr_matrix,
        "drawdown_windows": dd_windows,
        "defensive_currency_口径": {
            "cny_native": def_native_m,
            "usd_converted": def_usd_m,
        },
        "sleeve_metrics": {s: _metrics_block(sr[s]) for s in sr},
    }


def _merge_usq_into_panel(panel: PricePanel, usq_frame: pd.DataFrame) -> None:
    """Add month-end adj_close for us_quality tickers not already in the panel."""

    frame = usq_frame.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    for ticker, grp in frame.groupby("ticker"):
        if ticker in panel.monthly:
            continue
        s = grp.set_index("date")["adj_close"].astype(float).sort_index()
        me = _month_end_index(s)
        panel.monthly[str(ticker)] = {ts.date(): float(v) for ts, v in me.items()}


def _print_summary(r: dict[str, Any]) -> None:
    print("\n=== B106 组合层 uplift A/B (USD-unified, sleeve-return level) ===", file=sys.stderr)
    meth = r["methodology"]
    print(f"  window {meth['window']}  n={meth['n_months']}m", file=sys.stderr)
    header = "  scheme                    CAGR    AnnVol  Sharpe  MaxDD    Recov  FinalNAV"
    print(f"\n{header}", file=sys.stderr)
    for name, m in r["scheme_metrics"].items():
        print(
            f"  {name:24s} {m['cagr']*100:6.2f}% {m['ann_vol']*100:6.2f}% "
            f"{m['sharpe']:6.3f} {m['max_drawdown']*100:6.1f}% {m['recovery_gain']*100:6.1f}% "
            f"{m['final_nav']:7.3f}",
            file=sys.stderr,
        )
    print("\n  红利低波(defensive) vs attack sleeves correlation:", file=sys.stderr)
    print("    -- USD-converted (what a USD Master book actually experiences) --", file=sys.stderr)
    for k, v in r["correlations_defensive_vs_attack"].items():
        print(f"    {k:40s} {v:+.3f}", file=sys.stderr)
    print("    -- CNY-native defensive vs USD attack (market mismatch) --", file=sys.stderr)
    for k, v in r["correlations_defensive_cny_native_vs_attack"].items():
        print(f"    {k:40s} {v:+.3f}", file=sys.stderr)
    dc = r["defensive_currency_口径"]
    print("\n  defensive leg 口径 (CNY-native vs USD-converted):", file=sys.stderr)
    for k in ("cny_native", "usd_converted"):
        m = dc[k]
        print(f"    {k:14s} CAGR {m['cagr']*100:6.2f}% Sharpe {m['sharpe']:.3f} "
              f"MaxDD {m['max_drawdown']*100:5.1f}%", file=sys.stderr)
    v = r["verdict"]
    print(f"\n  VERDICT: {v['decision']} — {v['recommendation']}", file=sys.stderr)
    for row in v["ranked"]:
        gate = "PASS" if row["passes_gate"] else "fail"
        print(f"    {row['scheme']:24s} ΔSharpe {row['delta_sharpe']:+.3f} "
              f"ΔMaxDD {row['delta_maxdd']*100:+.1f}pp  gate={gate}", file=sys.stderr)


def main() -> int:
    results = run()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(results, ensure_ascii=False, indent=2, default=str) + "\n"
    RESULTS_JSON.write_text(payload, encoding="utf-8")
    _print_summary(results)
    print(f"\nwrote {RESULTS_JSON}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
