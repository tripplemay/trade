# B093 F001 — HK/China real-stock vs proxy-ETF decision rerun

**Batch:** B093 · **Feature:** F001 · **Type:** research-only (build phase)
**Gates BL-B011-S2 Batch 3** — whether to activate the `hk_china` live Master
with **real individual stocks** instead of the current ETF proxy.

> **Permanent boundary:** `hk_china` stays **ETF-proxy for LIVE**. This rerun
> touches NO production data path and NO Master live wiring. The only `trade/`
> edit is the B091-O1 close-NaN residual fix in `above_200d_ma` (with a
> zero-regression proof). Data reuses the cached `data/research/b090_hk` frame.

---

## 1. What changed since B090

1. **B091-O1 close-NaN residual FIXED** in
   `trade/strategies/hk_china_momentum/factors.py::above_200d_ma`. B091 fixed the
   200D-MA to each ticker's own calendar, but the compared close was still the
   **union frame's raw last row** (`wide.iloc[-1]`) — NaN whenever the union's
   last date is a trading holiday for a ticker → `close > ma == NaN` →
   `fillna(False)` → a spurious "below MA" / false-defensive. Fixed to each
   ticker's **own last valid close** (`wide.ffill().iloc[-1]`).
   - **Zero-regression proven:** on a single-calendar gap-free frame (the LIVE
     US-only proxy MCHI/FXI/KWEB/ASHR) `ffill` is a no-op, so the result is
     **byte-identical** to the pre-fix path. Pinned by
     `tests/unit/test_hk_china_close_nan_residual_fix.py::test_single_calendar_gap_free_is_byte_identical`.

2. **Matched `top_n`.** B090 compared proxy `top_n=2` vs real `top_n=6` —
   different breadth, so any edge conflated concentration with data-source. The
   proxy momentum engine **hard-caps `top_n` to {1, 2}** (design §8.2 "Top 1-2"),
   so the largest number of names BOTH engines can hold is **2**. The fair
   matched run is therefore **`top_n=2` on both sides**; the `top_n=6` real run is
   kept only as a reference to expose the breadth effect.

Runnable window: **SGOV pricing floor 2020-05-28 → 25 quarters (2020-06-30 …
2026-06-30)**.

---

## 2. The close-NaN residual — quantified honestly

Re-running the real sleeve's per-quarter decision with the FIXED close vs the
pre-fix BUGGY close over the 25 scored quarters:

| reason | FIXED (`ffill`) | BUGGY (`iloc[-1]`) |
|---|---|---|
| `selected_top_n` (participates) | 18/25 | 18/25 |
| `regional_risk_off` | 6/25 | 6/25 |
| `no_name_passed_trend` | 1/25 | 1/25 |
| **defensive total** | **7/25** | **7/25** |

**The fix removed 0 false-defensive quarters on this 25-quarter sample.**
Full end-to-end reruns confirm CAGR / Sharpe / MaxDD / defensive-count are
**byte-identical** fixed-vs-buggy at both `top_n=2` and `top_n=6`.

What the fix *does* correct: on exactly **one** quarter — **2023-09-29**, a
mainland-A holiday where the shared last row is an HK/US trading date and 10
A-share names carry NaN in that row — the buggy raw-last-row close flips **2**
individual `above_MA` signals to a spurious False (`600900.SH`, `601398.SH`).
Neither name was in the top-2 (or top-6) momentum ranks that quarter, so the
aggregate participate/defensive decision and the metrics never moved.

**Interpretation:** the fix is *correct and necessary* (it removes a genuine
cross-calendar artifact, proven on a constructed holiday frame and observed on 2
real signals) but it is **not outcome-changing on this particular sample**. The
task's "~2 quarters" estimate materialized as **2 ticker-signals on ~1 quarter**,
not 2 flipped defensive quarters. The residual is therefore confirmed gone and
confirmed immaterial to the verdict below.

---

## 3. Real vs proxy — the comparison tables

All numbers: USD caliber, same signal dates, same friction, 25 quarters
(2020-06-30 … 2026-06-30), SGOV defensive asset, full stock-history warmup.

### 3a. MATCHED `top_n=2` (fair — isolates data-source)

| metric | proxy (ETF ×2) | real (stock ×2) | real − proxy |
|---|---:|---:|---:|
| CAGR | **+2.75%** | +2.97% | +0.22pp |
| Sharpe | **+0.522** | +0.437 | **−0.085 (worse)** |
| annualized vol | +5.48% | +7.27% | +1.79pp (higher) |
| max drawdown | **−3.87%** | −9.20% | **−5.33pp (2.4× deeper)** |
| defensive periods | 12/25 | 7/25 | real participates more |
| forced-defensive | 0 | 0 | — |
| avg holdings | 1.04 | 1.44 | — |

### 3b. REFERENCE `top_n=6` real (B090 caliber — breadth gap, NOT fair)

| metric | proxy (ETF ×2) | real (stock ×6) | real − proxy |
|---|---:|---:|---:|
| CAGR | +2.75% | +2.75% | +0.00pp |
| Sharpe | +0.522 | **+0.616** | +0.094 (better) |
| annualized vol | +5.48% | **+4.57%** | −0.91pp (lower) |
| max drawdown | −3.87% | −5.07% | −1.20pp (deeper) |
| defensive periods | 12/25 | 7/25 | — |
| avg holdings | 1.04 | 4.08 | — |

**Real sleeve participation (holds stocks): 18/25 = 72.0%** on the full-history
warmed run (was 0% pre-B091; the close-NaN fix contributed 0 of the increase —
the lift is the full-history MA/momentum warmup, not the residual).

---

## 4. Reading the two tables

- **On the fair matched-breadth basis (3a), real does NOT beat the proxy.** Raw
  CAGR is a statistical tie (+0.22pp), but real is **worse on Sharpe** (0.44 vs
  0.52) and carries a **2.4× deeper max drawdown** (−9.2% vs −3.9%) with higher
  volatility. Two concentrated single names add risk without a risk-adjusted
  reward over the proxy's two diversified baskets.
- **The only apparent real edge is in the `top_n=6` reference (3b)** — better
  Sharpe and lower vol at the SAME CAGR. But that edge is a **breadth** effect
  (6 names diversify away idiosyncratic risk), not a data-source signal, and it
  **vanishes/reverses when breadth is matched** (3a). Attributing it to
  "individual stocks beat ETFs" would conflate concentration with data-source —
  exactly the confound the matched run controls for.

---

## 5. The four caveats, weighed

1. **SGOV inception floor (2020-05-28) → 25 quarters, single regime.** The whole
   runnable window is one China-bear-heavy cycle (2020 peak → 2022–24 drawdown →
   2025–26 partial recovery). 25 quarters is a thin sample and it is *not*
   regime-diverse — neither side has been tested across a China bull. Any Sharpe
   difference of <0.1 is well inside noise for n=25.
2. **Survivorship bias (upward, on real).** The 26-name universe is today's
   liquid names; historical index membership/liquidity was not reconstructed. The
   real sleeve's numbers are an **optimistic upper bound**. Even *with* that tail
   wind, real does not beat the proxy on a matched basis — which strengthens the
   NO-GO.
3. **Matched `top_n`.** Handled directly: `top_n=2` both sides (§3a). The proxy
   engine caps at 2, so 2 is the only honestly matchable breadth. The `top_n=6`
   result (§3b) is reported but explicitly discounted as a breadth artifact.
4. **Close-NaN residual (fixed).** Confirmed gone and confirmed immaterial to
   this sample (§2): 0 flipped defensive quarters, byte-identical metrics.

Additional standing caveat: **the proxy sleeve itself is weak** (CAGR +2.75%,
Sharpe 0.52 over a bear-heavy window). Real is being measured against a low bar
and still fails to clear it on a risk-adjusted, matched basis.

---

## 6. Verdict — **NO-GO** (INCONCLUSIVE-leaning)

**Do NOT activate real individual-stock `hk_china` for BL-B011-S2 Batch 3.
Keep the ETF proxy.**

On the only fair comparison (matched `top_n=2`) the real single-stock sleeve does
**not** beat the ETF proxy: essentially tied CAGR, **worse** Sharpe, higher vol,
and a **2.4× deeper drawdown** — and this is *with* a survivorship tail wind that
inflates the real side. The one favorable real reading (`top_n=6`) is a
breadth/diversification artifact that disappears at matched breadth, not evidence
that real data beats the proxy.

The evidence is also **insufficient to ever be a clean GO**: a 25-quarter,
SGOV-floored, single-China-bear-regime window with survivorship bias cannot
support activating live individual-stock trading — which carries real
operational cost (per-name execution, FX, corporate actions, borrow) that the
proxy avoids. There is no decision-grade upside to justify that cost/risk.

**Recommendation:** stay ETF-proxy for LIVE (the permanent boundary holds). If
this question is revisited, it needs (a) a point-in-time, survivorship-controlled
universe and (b) a longer / regime-diverse window than SGOV allows — neither of
which is available today.

---

## 7. Reproduction & gates

```bash
# Fix + tests (root venv)
./.venv/bin/python -m ruff check trade/strategies/hk_china_momentum/factors.py \
  tests/unit/test_hk_china_close_nan_residual_fix.py \
  scripts/research/b093_hk_china_decision_rerun.py          # All checks passed
./.venv/bin/python -m mypy trade                             # Success, 103 files
./.venv/bin/python -m pytest \
  tests/unit/test_hk_china_close_nan_residual_fix.py \
  tests/unit/test_hk_china_above_200d_ma_fix.py -q           # 5 passed

# Backend regression (after reinstall)
(cd workbench/backend && .venv/bin/python -m pip install ../.. -q)
workbench/backend/.venv/bin/python -m pytest \
  workbench/backend/tests/unit/test_strategies.py -q         # 13 passed

# The decision rerun (reuses cached b090 data; no re-fetch)
workbench/backend/.venv/bin/python -m scripts.research.b093_hk_china_decision_rerun
```

**Files**
- `trade/strategies/hk_china_momentum/factors.py` — B091-O1 close-NaN fix (`ffill().iloc[-1]`)
- `tests/unit/test_hk_china_close_nan_residual_fix.py` — multi-calendar fix + zero-regression byte-identical
- `scripts/research/b093_hk_china_decision_rerun.py` — matched-top_n rerun + residual quantification
- `docs/test-reports/B093-hk-china-decision-rerun.md` — this report
