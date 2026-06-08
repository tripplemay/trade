"""B047 — on-demand async backtest worker package.

A long-running worker (``worker.py``) polls the ``backtest_run`` queue, runs
the REAL ``trade`` Master Portfolio backtest engine + report generation, and
writes the result back to the DB. This is the only place (alongside the F004
canonical job) allowed to import ``trade`` for backtests — the request path
(``routes/services/backtests``) stays off the heavy stack (§12.10.2).

Boundary (r): deterministic backtest computation over read-only price data —
it never touches broker / order-ticket / execution surfaces.
"""
