# `data/fixtures/golden/` — committed **real-data** golden fixture (B071 F002)

A frozen, committed subset of **real** market data — the deterministic
foundation for CI backtest / recommendation assertions (B071 test-automation
roadmap Phase 1, 桶 A). Unlike the synthetic `_generate.py` fixtures
(`us_quality_momentum/`, `hk_china_momentum/`), every price and fundamental
here is a **real historical observation**, carved (not generated) from the
gitignored real-market-data snapshots under `data/snapshots/`.

- **Frozen:** 2026-06-21 (B071 F001→F004 batch).
- **Carved by:** [`_freeze.py`](./_freeze.py) — see "Non-regenerability" below.
- **Total size:** 3.74 MB (budget < 5 MB).

---

## Purpose

`workbench-testing-strategy.md §1` is fixture-first: real network / real data
never run in CI, so until now "does the real-data backtest still behave" could
only be checked by **one Codex real-machine pass per batch** (v0.9.21 lesson).
This golden set ends that: it freezes a real Tiingo price panel + real SEC
EDGAR fundamentals so that backtests and recommendation scoring become
**deterministic and CI-assertable** — same input → same output, no random, no
live wire. The recurring invariants (N-strategy pairwise-distinct, weights
sum to 1, no negative cash, defensive shares×mark≈equity, Master backwards-
compat) become **permanent acceptance regressions** (F003/F004) instead of
per-batch manual real-machine verification.

It is a **supplement**, not a replacement: the synthetic fixtures stay for the
deterministic unit baselines they already pin. Golden adds *real-data*
determinism on top.

---

## Files & provenance tiering (honest about what is real)

| File | Tier | Source | Schema (loader contract) |
|---|---|---|---|
| `prices_daily.csv` | **REAL market data** | real Tiingo OHLCV, carved from `data/snapshots/prices/unified/prices_daily.csv` | `date,ticker,open,high,low,close,adj_close,volume` (`PRICES_REQUIRED_COLUMNS` / `UNIFIED_REQUIRED_COLUMNS`) |
| `fundamentals.csv` | **REAL market data** | real SEC EDGAR XBRL ratios, carved from `data/snapshots/fundamentals/unified/fundamentals.csv` | 12 cols `report_date,ticker,fiscal_quarter,fiscal_quarter_end,roe,gross_margin,fcf_yield,debt_to_assets,pe,pb,ev_ebitda,earnings_yield` (`FUNDAMENTALS_REQUIRED_COLUMNS`) |
| `earnings_calendar.csv` | **DERIVED from real** | from `fundamentals.csv`: `earnings_date = report_date` (the SEC filing date) as a conservative, PIT-safe proxy — the real earnings announcement precedes the filing by days, so this errs late, never early | `ticker,earnings_date,fiscal_quarter,fiscal_quarter_end` (`EARNINGS_REQUIRED_COLUMNS`) |
| `universe.csv` | **STATIC metadata** | real-world GICS classifications (`name/exchange/gics_sector/gics_industry/listing_date`) carried over from the B025 `us_quality_momentum/universe.csv`, subset to the golden equity names. `market_cap_initial` is a **synthetic placeholder** inherited from that fixture (it is not market data) | `ticker,name,exchange,gics_sector,gics_industry,listing_date,market_cap_initial` (`UNIVERSE_REQUIRED_COLUMNS`) |

Values in the two REAL files are **byte-for-byte identical** to the snapshot
(`_freeze.py` reads/writes every cell as a raw string — no float re-parse, no
re-format), so the golden numbers are exactly the vendor's response.

---

## Universe (38 price tickers; 25 with fundamentals)

**25 quality names — real prices AND real SEC fundamentals** (drive us_quality
multi-factor selection, the master us_quality sleeve, the recommendation equity
slice):

```
AAPL AMT AMZN APD BAC CVX DUK ECL HD HON JNJ JPM KO LIN META
MSFT NEE NVDA PG PLD UNH UPS V WMT XOM
```

**13 ETF / defensive — real prices only** (drive the price-only records-based
engines: momentum, risk_parity, hk_china, master, plus recommendation scoring):

```
SPY QQQ VEA VWO EEM AGG IEF TLT GLD SGOV MCHI FXI KWEB
```

- `SPY VEA AGG GLD SGOV` = the risk_parity universe (+ master defensive `SGOV`).
- `QQQ VWO EEM` = momentum breadth (so momentum picks a basket ≠ risk_parity).
- `MCHI FXI KWEB` = hk_china proxies (so hk_china ≠ the US-equity strategies).
- `IEF TLT` = regime stabilisers.

This coverage is what makes **"N strategies, same window, pairwise-distinct"
non-degenerate**: us_quality (single stocks) ≠ momentum (ETF top-N) ≠
risk_parity (vol-target 5 ETF) ≠ hk_china (China proxies) ≠ master (blend),
because each consumes a structurally different basket.

---

## Windows (covers the two crisis regimes)

- **Prices:** 2019-01-02 → 2023-12-29 (~1258 trading days). Covers the
  **2020 COVID crash** (Feb–Mar 2020) and the **2022 bear market** — the regime
  / crisis windows the roadmap asks for.
- **Fundamentals:** filings 2014-01-31 → 2023-11-21. The lower bound reaches
  back to the snapshot's start so the PIT loader always has a visible (latest)
  filing during the price window even for names the SEC snapshot covers sparsely
  (see caveats). The loader's `effective_date = report_date + 1 business day`
  filter still enforces strict PIT visibility at each `as_of`.

---

## Non-regenerability (the key difference from synthetic `_generate.py`)

`_freeze.py` is a **provenance record, not a fresh-checkout regenerator.** It
carves from the real snapshots under `data/snapshots/`, which are **gitignored**
and **absent on a clean CI clone**. So:

- The golden CSVs are **committed** — you do **not** run `_freeze.py` to use
  them; CI and tests read the committed files directly.
- `_freeze.py` **cannot** reproduce them on a checkout without the real
  snapshots (it exits with a clear error). That is intentional: golden is a
  frozen photograph of real history, and `_freeze.py` documents exactly how the
  photograph was cropped (universe, windows, sort order, raw-string carve).
- Re-running it (on a machine that holds the snapshots) is **bit-identical** —
  deterministic sort + raw-string passthrough — so a refresh never silently
  perturbs the committed numbers.

---

## Honest coverage caveats (do not over-claim)

1. **CAT, GOOGL excluded.** The committed SEC snapshot holds no 10-K/10-Q for
   CAT before 2026-04 nor GOOGL before 2024-07 — neither has *any* fundamental
   visible during 2019-2023, so they cannot participate in the quality factor
   pipeline. Dropping them loses no GICS sector (HON/UPS cover Industrials, META
   covers Communication Services). They are simply absent from golden.
2. **BAC, LIN have no visible fundamental in early 2019** (BAC's first snapshot
   filing lands mid-2019; LIN is the 2018-10 Linde plc entity, so no pre-2019
   filings). Real PIT behaviour — those names enter the quality universe a few
   months into the window. Still non-degenerate (≥23 names throughout).
3. **Per-ticker fundamentals sparsity.** Some names (e.g. META: 2014-2017 then
   2023+; ECL: 2014 then 2023+) carry a stale-but-real pre-window filing as the
   latest-visible for part of the window. This is a snapshot-completeness
   artifact (missed intermediate filings), not a value error — it is still real,
   deterministic data.
4. **ASHR, DBC absent.** Two tickers in the workbench `ETF_UNIVERSE`
   (`data_refresh.refresh.ETF_UNIVERSE`) are not in the real 52-ticker snapshot,
   so golden cannot include them. Golden is the **real-available subset** of the
   recommendation universe; regime's stabilizer set is slightly narrower on
   golden. Not a blocker (regime_adaptive is INACTIVE; hk_china uses
   MCHI/FXI/KWEB, not ASHR).
5. **cn_attack (A-share) intentionally NOT in golden.** A-share PIT universe +
   CSI300 are not in the US Tiingo/SEC snapshots, and pulling them in would
   break the <5 MB + real-available boundary. Golden's deterministic targets are
   the **US engines** (master / us_quality / risk_parity / momentum / hk_china);
   cn_attack stays on its own research data (graceful-degradation when absent).

---

_Disclaimer: research-only. Golden is committed test data; it never touches
the production data path (`data/snapshots/` unified files / `WORKBENCH_DATA_ROOT`)
and never authorizes paper or live trading._
