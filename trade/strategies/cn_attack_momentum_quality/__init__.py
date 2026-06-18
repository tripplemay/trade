"""B066 — A-share attack momentum+quality strategy package (research-only, P1).

A pure-attack A-share single-stock selection engine (always fully invested in the
top-N, **no market-regime defensive gate** — the hk_china_real "200D gate hid
behind cash and never tested the thesis" lesson, B063). It mirrors the B025 US
Quality Momentum primitives — ``momentum_12_1`` and ``quality_score`` are reused
verbatim (PIT-aware, as-of safe) — over an A-share point-in-time universe
(:mod:`trade.data.cn_attack_universe`) scored on the same unified prices/CAS
fundamentals CSVs (B062 + B065), and offers a clean 2-factor A/B test:

- variant ``quality_momentum`` — momentum blended with the CAS quality score
  (a ticker must have fundamentals to qualify → a soft quality filter);
- variant ``pure_momentum`` — momentum only (fundamentals not required) →
  measures whether quality actually adds value on A-shares.

P1 boundary (research-only): engine + multi-variant backtest validation; **no live
advisory / execution / broker surface** (that is P2). F002 adds the daily-monitor
no-trade-band driver, the 3 exit variants, and the directional A-share cost model.
"""
