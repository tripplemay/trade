# `data/snapshots/news/` — news ingest raw bodies (B033)

This directory is the on-disk staging area for B033 news ingest. Raw
SEC filings (10-K / 10-Q / 8-K primary documents, Form 4 XML) and
Yahoo Finance RSS per-entry XML fragments land here, partitioned by
source + filing date. The `news` table in the workbench DB stores
only the path + sha256; permanent product boundary **(p)** keeps raw
text out of DB columns.

## Layout

```
data/snapshots/news/
├── README.md
├── sec_edgar/
│   └── YYYY-MM-DD/                # filingDate from /submissions/
│       ├── {accession_no}.htm     # 10-K / 10-Q / 8-K primary doc
│       └── {accession_no}.xml     # Form 4 primary doc
└── yahoo_rss/
    └── YYYY-MM-DD/                # pubDate from RSS item
        └── {sha256(guid)[:16]}.xml  # per-entry XML fragment
```

## Production CLI entrypoint

```bash
# Fetch the last 30 days from both sources for the full universe.
SEC_EDGAR_CONTACT_EMAIL=ops@yourdomain.com \
  python -m workbench_api.news.cli fetch --source all

# Narrow to one source / one ticker / one form type.
python -m workbench_api.news.cli fetch \
  --source edgar --ticker AAPL --form-types 10-K --since 2026-01-01

python -m workbench_api.news.cli fetch \
  --source yahoo --ticker SPY --since 2026-04-01
```

The CLI is **manual-trigger only** in B033 — there is no cron, no
APScheduler, no GitHub Actions scheduled workflow. Permanent product
boundary **(q)** locks this in; see
`workbench/backend/tests/safety/test_news_no_scheduler.py`. A future
batch that wants automated scheduling must add a permanent-boundary
relaxation note before introducing a scheduler module.

## Production location

On the production VM the canonical store is the **persistent** path
`/var/lib/workbench/data/snapshots/news` — next to the SQLite DB
(`/var/lib/workbench/db/workbench.db`), so raw bodies survive release
swaps and the 30-day release GC. `workbench/deploy/scripts/deploy.sh`
creates it (empty) on every deploy and symlinks the release-relative
`data/snapshots/news` path onto it. The directory is created but never
populated by the deploy — ingest is manual-trigger only (boundary `(q)`).
Override the location with `WORKBENCH_NEWS_SNAPSHOT_DIR` if the data root
ever moves. Guard: `tests/safety/test_news_snapshot_dir_provisioned.py`.

## Why `data/snapshots/`?

Same regenerate-don't-commit semantics as `data/snapshots/prices/`
(B028) and `data/snapshots/fundamentals/` (B029). The parent
`.gitignore` ignores `*.htm` / `*.html` / `*.xml` under this tree so
the on-disk corpus stays out of git; only this README + the empty
`{sec_edgar,yahoo_rss}/` directory layout ships.

## What B034+ does with these

B034 (Stream 2.B News↔ticker + Cohere embedding) reads from the
`news` table, joins by `ticker` / `published_at`, fans out the text
to the embedding service, and persists `ticker_mentions` JSONB +
embedding vectors. The raw bodies stay on disk; only metadata +
embeddings are read by the AI advisor.
