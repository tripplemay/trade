# US Quality Momentum (27 real tickers) — fixture vs real (2026-05-27)

**Sleeve id:** `us_quality`
**Universe size:** 27

**Methodology note:** Equal-weight buy-and-hold proxy across the sleeve's universe. Captures data-source quality delta; strategy-logic correctness is pinned by the existing test suite under FORCE_FIXTURE_PATH=1.

## Side-by-side metrics

| Metric | Fixture (synthetic) | Real (unified) | Δ (real − fixture) |
|---|---:|---:|---:|
| Annual Return | 14.86% | 30.73% | +15.88pp |
| Volatility | 6.93% | 26.21% | +19.28pp |
| Sharpe | 2.14 | 1.17 | -0.97 |
| Sortino | 3.40 | 1.54 | -1.86 |
| Calmar | 2.07 | 0.73 | -1.34 |
| Max Drawdown | -7.18% | -41.98% | -34.80pp |
| Win Rate | 55.19% | 55.89% | +0.70pp |

_Daily return rows used:_ fixture=2892, real=3115

_Universe tickers resolved:_ fixture=27/27, real=27/27
