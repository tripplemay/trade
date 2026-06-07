"""B048 F001 — price-history backfill package.

A scheduler job (CLI, runnable on the ``workbench-data-refresh`` cadence)
reads the B045 unified prices CSV
(``<data_root>/snapshots/prices/unified/prices_daily.csv``) and
materialises the **deep** daily close history into the ``price_history``
table. The B048 safety / risk layer (F003) then reconstructs a
mark-to-market NAV time series from this table to compute master +
per-sleeve drawdown over time.

Boundary (r): read-only data job — it reads a CSV the B045 refresh job
already wrote (§12.10 job reads CSV, writes DB) and never touches broker /
order-ticket / execution surfaces (the scheduler-scope guard enforces
this by scanning this package). The request path only ever *reads*
``price_history`` via :class:`PriceHistoryRepository`.
"""
