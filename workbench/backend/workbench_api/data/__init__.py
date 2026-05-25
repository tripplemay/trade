"""B027 — real-market-data ingest module.

Houses the vendor-agnostic ``SnapshotLoader`` abstraction plus per-vendor
implementations (currently only ``TiingoSnapshotLoader``). Strategy code
continues to read fixtures via ``trade/data/loader.py``; this module is
where real market data lands once Phase 1 (B027-B030) wires the cutover.

Boundary: this module is the only place that imports an external market-
data HTTP API. Strategy code, route handlers, and tests must depend on
the ``SnapshotLoader`` abstraction so a future vendor switch only touches
the adapter file.
"""
