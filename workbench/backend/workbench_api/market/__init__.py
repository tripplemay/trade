"""B035 — market-context domain (FRED + Alpha Vantage daily read-only fetch).

Houses the manual / systemd-timer-driven CLI that pulls the market-context
series into the snapshot foundation + DB. Permanent product boundary
**(r)** (B035 spec §3): the only scheduler the project runs is the
market-context timer, and it does **read-only data fetching only** — it
never imports or invokes broker / order-ticket / execution /
recommendation / LLM code. The guard test
``tests/safety/test_market_scheduler_scope.py`` enforces that.
"""
