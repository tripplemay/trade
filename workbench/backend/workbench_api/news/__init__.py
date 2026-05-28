"""B033 news ingest framework — metadata + snapshot path only.

Permanent product boundary **(q)**: this package never grows a
``scheduler.py`` / cron / APScheduler integration. Production ingest
runs through ``python -m workbench_api.news.cli fetch`` triggered
manually. The guard test
``tests/safety/test_news_no_scheduler.py`` enforces that — a future
batch that wants automated scheduling must first add a permanent
boundary relaxation note.

The package layout follows Stream 2.A scope:
- ``snapshot``: write raw filing / article body to disk + compute sha256
- ``adapters.base``: shared :class:`NewsItem` DTO + :class:`NewsAdapter` Protocol
- ``adapters.sec_edgar`` (F002): SEC EDGAR ``/submissions/`` adapter
- ``adapters.yahoo_rss`` (F003): Yahoo Finance RSS adapter
- ``cli`` (F003): argparse fetch entrypoint
"""
