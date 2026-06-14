"""B063 F002 — real-data HK-China momentum (research-only, point-in-time).

The proxy sleeve (:mod:`trade.strategies.hk_china_momentum`) trades four
US-listed ETFs and feeds the live Master. This package is its **research
counterpart**: it runs the *same* price-only momentum + trend + regional-risk
factors over a **wide, multi-sector universe of real A-share + HK individual
stocks** (:data:`trade.data.hk_china_real_universe.REAL_HK_CHINA_UNIVERSE`),
selects the top names point-in-time, and works in USD so a B063 backtest is
directly comparable to the USD proxy.

It is **purely additive** — nothing here is wired into the Master or any live
recommendation. It exists only to produce the B063 decision report (is real
exposure worth the FX/concentration complexity vs the proxy?).
"""
