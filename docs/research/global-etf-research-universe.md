# Global ETF Research Universe

This file documents the committed research-only ETF universe in `trade/data/fixtures/research_universe.json`.

The universe is for offline research and backtest development only. It is not a trading recommendation, not a live-trading allowlist, and not evidence that any instrument is approved for broker execution.

## Data Dictionary

| Field | Meaning |
|---|---|
| `ticker` | ETF ticker symbol used for research identification. |
| `name` | Human-readable fund name. |
| `asset_class` | Research sleeve such as `global_equity`, `us_equity`, `ex_us_equity`, `bonds`, `gold_commodity`, or `cash_defensive`. |
| `region` | Primary geographic exposure label. |
| `currency` | Trading/reporting currency for the research instrument. |
| `role` | Intended research role in Global ETF Momentum studies. |
| `inception_date` | Best-effort public inception date when known; not used as PIT production data. |
| `data_source_policy` | Safe data sourcing rule. Required CI remains fixture/mock-first and offline. |
| `research_notes` | Review notes and limitations for future research. |

## Current Coverage

- Global equity: `VT`
- US equity: `SPY`, `QQQ`
- Ex-US equity: `VEA`, `EEM`
- Bonds: `AGG`, `TLT`
- Gold/commodity: `GLD`, `DBC`
- Cash/defensive: `SGOV`

## Safety Boundary

- No paid data is committed.
- No broker export or account data is committed.
- Optional public data, if introduced, must remain manual, best-effort, disabled by default, and excluded from required CI.
- This universe does not create paper/live execution capability.
