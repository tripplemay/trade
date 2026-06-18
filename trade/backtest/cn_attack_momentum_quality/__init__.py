"""B066 — A-share attack momentum+quality backtest package (research-only, P1).

A daily-monitor / no-trade-band backtest engine for the CN attack strategy
(:mod:`trade.strategies.cn_attack_momentum_quality`). Distinct from the US single
-sleeve engine in three A-share-specific ways the spec calls out:

- **directional costs** (:mod:`.costs`) — A-share stamp duty is charged on *sells
  only* (0.1%), so a symmetric friction rate cannot express it;
- **daily driver + no-trade band** — the target is recomputed every trading day
  but the portfolio only rebalances when the would-be turnover exceeds a band, so
  most days hold (true turnover/cost emerge from the simulated daily loop);
- **3 exit variants** — momentum-decay (base), trailing-stop, and hard-profit
  -target — compared head-to-head (F003 walk-forward picks the net-best).

US zero-regression by construction: this package never imports or mutates the US
backtest engine; it reuses only the shared metrics module.
"""
