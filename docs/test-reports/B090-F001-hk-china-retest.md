# B090 F001 — HK/China real-vs-proxy retest (200D-warmup methodology fix)

**Batch:** B090 F001 (research-only; touches NO strategy/flagship/production code)
**Run date:** 2026-07-05 · akshare 1.18.64 · pandas 3.0.3
**Scripts:** `scripts/research/b090_hk_china_fetch.py`, `scripts/research/b090_hk_china_retest.py`
**Verdict:** **NO-GO for the real sleeve as implemented / INCONCLUSIVE on the underlying question.** The 200D-warmup hypothesis is **falsified** — warmup does not change the real strategy's outcome. The real cause of "real = 100% defensive" is a **calendar-misalignment bug** in the shared `above_200d_ma` factor, not warmup. The real strategy never held a single stock, so this run is **not** evidence that real HK/China stocks lack edge.

---

## 1. Why this retest

B063's real-vs-proxy comparison found the real individual-stock strategy went defensive on ~20/20 quarters (0 stock picks). The stated hypothesis was **MA warmup**: the fetched frame started at the scored window, so the first ~200 trading days had no 200D-MA history and the trend gate forced defensive artificially. The fix under test: fetch **full price history** (≥200 trading days of warmup before the first scored quarter) so the MA/momentum gates are warm and the real strategy can participate. Then compare real-vs-proxy honestly.

## 2. Data coverage (fetch)

| Sleeve | Source | Coverage |
|---|---|---|
| 16 HK stocks | `akshare.stock_hk_daily(<5-digit>, qfq)` | 16/16 |
| 10 mainland A-share | `akshare.stock_zh_a_daily(sh/sz+code, qfq)`¹ | 10/10 |
| 4 proxy ETFs (MCHI/FXI/KWEB/ASHR) | `akshare.stock_us_daily(qfq)` | 4/4 |
| SGOV (shared defensive) | `akshare.stock_us_daily(qfq)` | 1/1 |
| **Total prices** | | **31/31 tickers, 130,371 rows** |
| FX HKD (FRED DEXHKUS) | public CSV, no key | 11,413 obs |
| FX CNY (FRED DEXCHUS) | public CSV, no key | 11,353 obs |

¹ The task's literal "26 HK via stock_hk_daily" is imprecise — 10 of the 26 are mainland A-shares (`.SH`/`.SZ`), and the FRED **DEXCHUS (CNY)** requirement confirms they must be fetched in CNY. A-shares use the sina host (`stock_zh_a_daily`) because eastmoney's `stock_zh_a_hist` was SSL/rate-limit flaky at run time.

**Windows.** Full shared (proxy∩real equity) calendar: **86 quarter-end signals, 2005-03-31 … 2026-06-30**. Full stock history reaches back to 2001–2004 (HK) / 1998 (some A-shares) — i.e. the warmup fix (full history) **was** applied.

## 3. The binding constraint: SGOV inception floors the window to 2020

SGOV (the shared defensive asset for **both** sleeves) only lists from **2020-05-28**. A defensive quarter before that cannot be priced — the backtest engine `KeyError`s on `('SGOV', <date>)`. So the runnable scored window is floored at SGOV inception: **25 quarters, 2020-06-30 … 2026-06-30**. (The task-literal "200th shared trading day" filter cutoff is 2005-10-21, which is **subsumed** by this stricter 2020 floor, so it drops no additional signals.)

## 4. Warmup fix effect (real strategy, identical signal dates both runs)

| | NO-WARMUP (history truncated to 2020-05-28) | WITH-WARMUP (full history to 2001–2004) |
|---|---|---|
| real `defensive_periods` | **25 / 25** | **25 / 25** |
| real `forced_defensive_periods` | 0 / 25 | 0 / 25 |
| real avg names **scored**/qtr | 19.36 | 23.12 |
| real avg **holdings**/qtr | **0.00** | **0.00** |

**The warmup fix changed the real defensive count by 0.** Full history raised how many names get *scored* (19→23, as expected) but the strategy still went **100% defensive every quarter** and held **zero stocks**. → **The warmup hypothesis is falsified.**

## 5. Proxy vs Real (WITH-WARMUP — the methodology-correct run, 25 quarters)

| metric | proxy (4 ETFs) | real (26 names) |
|---|---|---|
| CAGR | **+2.75%** | +0.03% |
| Sharpe | +0.52 | +0.997 ⚠️ |
| annualized vol | 5.48% | 0.03% |
| max drawdown | −3.87% | −0.04% |
| defensive_periods | 12 / 25 | **25 / 25** |
| forced_defensive_periods | 0 | 0 |
| avg holdings | 1.04 baskets | **0.00 stocks** |

⚠️ **The real Sharpe of ~1.0 is an artifact, not an edge.** The real curve is **100% SGOV cash** every quarter — a near-riskless T-bill ETF — so its "Sharpe" just reflects bond carry with ~0 vol. It must **not** be read as the real sleeve outperforming. The real sleeve never took equity risk.

## 6. Root cause — calendar misalignment in `above_200d_ma` (NOT warmup)

Defensive-reason breakdown (with-warmup): **`regional_risk_off` = 25/25.** The regional risk-off gate fires because all three bellwethers (0700.HK / 9988.HK / 600519.SH) read as "below 200D MA" every single quarter — implausible for Tencent across the 2020, 2024 and 2025 rallies.

Root-cause probe (as-of 2025-06-30, when Tencent was clearly uptrending):

| bellwether | non-NaN in last 200 **rows** (union calendar) | above MA (union frame) | above MA (HK-only frame) |
|---|---|---|---|
| 0700.HK | 188 / 200 | **False** | **True** |
| 9988.HK | 188 / 200 | **False** | **True** |
| 600519.SH | 184 / 200 | **False** | n/a |

`above_200d_ma` builds a wide `date × ticker` frame from the **union** of the HK, mainland-A and US(SGOV) trading calendars, then rolls a **200-row** window with `min_periods=200`. Cross-market-only dates (HK closed while mainland/US open, etc.) inject NaNs, so any ticker only has ~184–188 non-NaN observations inside a 200-row window → the 200D-MA is **permanently NaN** → the ticker reads "below MA" forever → `regional_risk_off` fires every quarter → the real sleeve sits 100% in SGOV.

Notably, the momentum **scoring** works fine (avg 23 names scored) because `composite_momentum` uses an as-of **month** lookup, not a fixed-row rolling window — it is robust to calendar gaps. The bug is **specific to the fixed-row 200D-MA window** meeting a genuinely multi-calendar universe. (An HK-only single-calendar frame computes a valid MA and `above=True`, per the probe.)

This is very likely the **actual** reason B063 saw ~20/20 defensive — a structural factor/data bug, mis-attributed at the time to MA warmup.

## 7. Verdict

- **NO-GO** for the real HK/China sleeve **as currently implemented**: it is structurally forced 100% defensive by a calendar-misalignment bug and never holds a stock. Providing full-history warmup does not fix it.
- **INCONCLUSIVE** on the underlying research question (is real A-share + HK exposure worth the FX/concentration complexity vs the proxy?): the real strategy never actually participated, so this run yields **no** clean evidence either way. The proxy sleeve over the same 2020–2026 window is itself weak (CAGR +2.75%, Sharpe 0.52 — a China-bear-heavy sample).
- **Actionable next step (out of scope here — would touch `trade/`):** fix `above_200d_ma` (and any other fixed-row-window factor) to compute the MA on each ticker's own trading calendar (e.g. drop per-ticker NaNs before rolling, or use a calendar-day / min_periods-relaxed window) before any real-vs-proxy conclusion can be drawn. That is a strategy-code change and must go through the normal spec → build → verify flow.

## 8. Honest caveats

1. **qfq ≈ adj_close, not identical to Tiingo.** All prices use akshare qfq-adjusted close as both `close` and `adj_close`. Direction/momentum preserved, but not the exact total-return series the live flagship uses (Tiingo).
2. **Short, biased window.** Only ~6 years / 25 quarters (2020-06 … 2026-06) are runnable because SGOV lists from 2020-05-28; the sample is heavily weighted to the 2021–2024 China equity bear market.
3. **Residual selection bias.** The 26-name real universe is names liquid **today**; historical index membership is not reconstructed, so any real edge would be an optimistic upper bound.
4. **Real Sharpe is cash carry**, not skill (see §5).
5. **A-share source** is sina `stock_zh_a_daily` (eastmoney was SSL-flaky); FX is FRED daily forward-filled as-of.

## 9. Reproduce

```bash
# fetch (writes data/research/b090_hk/ — gitignored)
workbench/backend/.venv/bin/python -m scripts.research.b090_hk_china_fetch
# retest
workbench/backend/.venv/bin/python -m scripts.research.b090_hk_china_retest
# gates
./.venv/bin/python -m ruff check scripts/research/b090_hk_china_fetch.py \
    scripts/research/b090_hk_china_retest.py tests/unit/test_b090_hk_china_retest.py
./.venv/bin/python -m pytest tests/unit/test_b090_hk_china_retest.py -q
```
