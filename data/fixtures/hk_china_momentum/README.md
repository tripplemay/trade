# HK-China Momentum fixture (BL-B011-S2, synthetic)

**All data here is synthetic** — a deterministic geometric random walk per
ETF (`_generate.py`). It is NOT real market data and must never be presented
as backtest performance evidence. It exists so the strategy + master
integration tests run without the unified real-data CSV (CI without a
B045 data-refresh run).

## Files

- `universe.csv` — the Phase 1 US-listed China/HK ETF universe
  (`ticker,name,exposure,listing_date`). Price-only strategy → no sector /
  fundamentals columns.
- `prices_daily.csv` — long-format daily OHLCV (`date,ticker,open,high,low,
  close,adj_close,volume`), same 8-column schema as the unified CSV so the
  loader swaps sources without conversion. 460 trading days from 2023-01-02
  (≥ 252 for 12-month momentum + 200 for the 200-day MA window).

## Synthetic regimes (for deterministic strategy tests)

| ETF | trend | so tests can exercise |
|---|---|---|
| KWEB | strong up | top-1/2 selection, passes trend filter, KWEB sub-limit |
| MCHI | moderate up | passes trend filter |
| FXI | mild | borderline trend |
| ASHR | down | fails trend filter / regional-risk → defensive |

## Regenerate

```bash
python data/fixtures/hk_china_momentum/_generate.py
```

Output is byte-stable (fixed per-ticker seeds). The real source on the VM
is the B045 data-refresh unified CSV (MCHI/FXI/KWEB/ASHR were added to
`data_refresh.ETF_UNIVERSE` in F001); this fixture is the fall-back only.
