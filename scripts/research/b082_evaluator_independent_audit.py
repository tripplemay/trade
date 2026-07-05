"""B082 F004 evaluator — INDEPENDENT recomputation (plain pandas, no trade.* imports).

Re-derives the primary-口径 numbers from the frozen CSVs to cross-check the generator's
engine/report. Deliberately reimplements the dividend-yield reconstruction, spread,
three-tier rule, T+1 monthly sim, and window drawdowns from scratch so an engine bug
would show up as a mismatch. Prints a hand-check of one TR-PR dividend-yield point.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

D = Path("data/research/b082")
LOOKBACK = 252
SAT, HALF = 2.5, 1.5
W_LOW, W_HALF, W_FULL = 0.25, 0.5, 1.0


def load(name: str, col: str) -> pd.Series:
    f = pd.read_csv(D / f"{name}.csv", parse_dates=["date"])
    s = f.set_index("date")[col].astype(float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s


def tier(spread: float) -> float:
    if spread != spread:
        return W_LOW
    if spread >= SAT:
        return W_FULL
    if spread >= HALF:
        return W_HALF
    return W_LOW


def max_dd(equity: pd.Series) -> float:
    rm = equity.cummax()
    return float((equity / rm - 1.0).min())


def window_dd(equity: pd.Series, a: date, b: date) -> float:
    w = equity[(equity.index >= pd.Timestamp(a)) & (equity.index <= pd.Timestamp(b))]
    return max_dd(w)


tr = load("index_h20269", "close")
pr = load("index_h30269", "close")
y10 = load("cn_10y_yield", "yield")
hs300 = load("hs300", "close")

# --- dividend yield = trailing 252-obs TR return - PR return (percent) --- #
common = tr.index.intersection(pr.index)
trc, prc = tr.reindex(common), pr.reindex(common)
divy = ((trc / trc.shift(LOOKBACK) - 1.0) - (prc / prc.shift(LOOKBACK) - 1.0)) * 100.0
divy = divy.dropna()
print(f"divy: first={divy.index[0].date()} last={divy.index[-1].date()} "
      f"min={divy.min():.3f} mean={divy.mean():.3f} max={divy.max():.3f}")

# hand-check ONE point (the latest)
d = divy.index[-1]
i = common.get_loc(d)
tr_now, tr_then = trc.iloc[i], trc.iloc[i - LOOKBACK]
pr_now, pr_then = prc.iloc[i], prc.iloc[i - LOOKBACK]
hand = ((tr_now / tr_then - 1.0) - (pr_now / pr_then - 1.0)) * 100.0
print(f"HAND-CHECK {d.date()}: TR {tr_then:.2f}->{tr_now:.2f} ({tr_now/tr_then-1:+.4%}) "
      f"PR {pr_then:.2f}->{pr_now:.2f} ({pr_now/pr_then-1:+.4%}) "
      f"=> divy={hand:.4f}%  (series={divy.iloc[-1]:.4f}%)")

# --- spread + tiers --- #
y10a = y10.reindex(divy.index.union(y10.index)).ffill().reindex(divy.index)
spread = (divy - y10a).dropna()
_y10_last = y10a.reindex(spread.index).iloc[-1]
print(
    f"spread latest={spread.iloc[-1]:.3f}%  "
    f"(divy {divy.iloc[-1]:.3f} - y10 {_y10_last:.3f})"
)

monthly = spread.resample("ME").last().dropna()
targets = monthly.map(tier)
counts = {"full>=2.5": int((targets >= W_FULL).sum()),
          "half": int(((targets > W_LOW) & (targets < W_FULL)).sum()),
          "low<1.5": int((targets <= W_LOW).sum())}
print(f"n_month_ends={len(targets)} tier_counts={counts} latest_target={targets.iloc[-1]}")


# --- independent T+1 monthly sim on TR index (fractional, no cost) --- #
def simulate(prices: pd.Series, targ: pd.Series) -> pd.Series:
    idx = list(prices.index)
    ts_vals = [t.value for t in idx]
    exec_map: dict[pd.Timestamp, float] = {}
    for sig_date, w in targ.items():
        pos = pd.Series(ts_vals).searchsorted(pd.Timestamp(sig_date).value, side="right")
        if pos < len(idx):
            exec_map[idx[pos]] = float(w)
    units, cash = 0.0, 1.0
    eq = []
    for day in idx:
        p = float(prices.loc[day])
        pv = units * p + cash
        if day in exec_map:
            dv = exec_map[day] * pv
            units = dv / p
            cash = pv - units * p
        eq.append(units * p + cash)
    return pd.Series(eq, index=prices.index)


def cagr(eq: pd.Series) -> float:
    yrs = (eq.index[-1] - eq.index[0]).days / 365.25
    return (eq.iloc[-1] / eq.iloc[0]) ** (1 / yrs) - 1.0


hold = pd.Series(1.0, index=targets.index)
eq_s = simulate(tr, targets)
eq_h = simulate(tr, hold)
print(
    f"\nPRIMARY strategy : CAGR {cagr(eq_s):+.4%} "
    f"MaxDD {max_dd(eq_s):+.4%} end={eq_s.iloc[-1]:.4f}"
)
print(
    f"PRIMARY buy_hold : CAGR {cagr(eq_h):+.4%} "
    f"MaxDD {max_dd(eq_h):+.4%} end={eq_h.iloc[-1]:.4f}"
)

W22 = (date(2022, 1, 1), date(2022, 12, 31))
W24 = (date(2024, 1, 1), date(2024, 2, 29))
print(
    f"\n2022  DD: strat {window_dd(eq_s, *W22):+.4%} "
    f"hold {window_dd(eq_h, *W22):+.4%} hs300 {window_dd(hs300, *W22):+.4%}"
)
print(
    f"2024F DD: strat {window_dd(eq_s, *W24):+.4%} "
    f"hold {window_dd(eq_h, *W24):+.4%} hs300 {window_dd(hs300, *W24):+.4%}"
)


def wret(s: pd.Series, a: date, b: date) -> float:
    sub = s[(s.index >= pd.Timestamp(a)) & (s.index <= pd.Timestamp(b))]
    return sub.iloc[-1] / sub.iloc[0] - 1.0


print(
    f"2022  ret: strat {wret(eq_s, *W22):+.4%} "
    f"hold {wret(eq_h, *W22):+.4%} hs300 {wret(hs300, *W22):+.4%}"
)
print(
    f"2024F ret: strat {wret(eq_s, *W24):+.4%} "
    f"hold {wret(eq_h, *W24):+.4%} hs300 {wret(hs300, *W24):+.4%}"
)
