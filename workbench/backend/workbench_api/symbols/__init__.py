"""B059 — symbol information lookup (research-only EOD price / fundamentals / news).

Request-path safe: nothing in this package imports the ``trade`` package
(§12.10.2) or any broker SDK. F001 ships the price surface (provider
abstraction + on-demand fetch + cache + rate-limit guard + stats);
fundamentals (F003) and news (F004) extend it within the same batch.
"""
