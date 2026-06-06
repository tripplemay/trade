"""B045 — real-data refresh pipeline package.

A daily scheduler job (``workbench-data-refresh`` timer) fetches real prices
(Tiingo, B027) + fundamentals (SEC EDGAR, B029) for the Master Portfolio
universe and writes them as unified CSVs into the VM data store, in the exact
schema the ``trade`` loaders read. This lets the B044 recommendations
precompute score the full sleeve set on real data (``data_source=real``)
instead of the bundled fixture (B044 §Soft-watch S2/S3).

Boundary (r): read-only market-data fetch — it never touches broker /
order-ticket / execution surfaces (scheduler-scope guard enforces). The job
writes to the VM data dir (not repo-root) — §12.10 self-contained.
"""
