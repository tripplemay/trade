"""B033 F001 — NewsRepository.

Wraps the ``news`` table with the four operations the F002 / F003
adapters and the F003 CLI actually need:

- :meth:`save_if_new` — idempotent insert by ``(source, source_id)``;
  returns ``None`` when the row already exists. EDGAR accession numbers
  and Yahoo RSS GUIDs are stable upstream identifiers, so re-running an
  adapter is a no-op rather than a duplicate insert.
- :meth:`list_by_ticker` / :meth:`list_by_source` — filtered listings
  with ``since`` + ``limit`` knobs; ordered newest-first because the
  B034 Recommendations renderer and the F003 CLI both want recent
  filings at the top.
- :meth:`get_by_source_and_source_id` — direct lookup used by
  ``save_if_new`` and exposed for callers that want to ask "do we
  already have this filing?" without doing the insert.

The repository does **not** write to disk — the adapter is expected
to call :class:`workbench_api.news.snapshot.NewsSnapshotWriter` first
and pass the resulting ``snapshot_path`` + ``content_sha256`` into
:meth:`save_if_new`. That split keeps each layer single-purpose; a
test can exercise the repo against an in-memory SQLite DB without
touching the filesystem.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select

from workbench_api.db.models.news import News
from workbench_api.db.repositories.base import Repository
from workbench_api.news.adapters.base import NewsItem


class NewsRepository(Repository[News, UUID]):
    model = News
    primary_key_attr = "id"

    def get_by_source_and_source_id(self, source: str, source_id: str) -> News | None:
        stmt = select(News).where(
            News.source == source,
            News.source_id == source_id,
        )
        return self._session.execute(stmt).scalar_one_or_none()

    def save_if_new(
        self,
        item: NewsItem,
        *,
        snapshot_path: str,
        content_sha256: str,
        fetched_at: datetime | None = None,
    ) -> News | None:
        """Insert ``item`` if absent, return ``None`` if a row with the
        same ``(source, source_id)`` already exists.

        ``fetched_at`` defaults to ``datetime.now(timezone.utc)`` so the
        caller can override it deterministically from tests. The
        snapshot path + sha256 are passed in rather than computed here
        because the adapter has already written the body to disk before
        calling ``save_if_new`` (see module docstring).
        """

        if self.get_by_source_and_source_id(item.source, item.source_id) is not None:
            return None
        row = News(
            id=uuid4(),
            source=item.source,
            source_id=item.source_id,
            url=item.url,
            title=item.title,
            summary=item.summary,
            ticker=item.ticker,
            form_type=item.form_type,
            published_at=item.published_at,
            fetched_at=fetched_at or datetime.now(UTC),
            snapshot_path=snapshot_path,
            content_sha256=content_sha256,
            ticker_mentions=None,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def touch_latest_fetched_at(
        self, ticker: str, *, source: str, fetched_at: datetime
    ) -> bool:
        """B064 F002 — advance the newest (ticker, source) row's ``fetched_at``
        to ``fetched_at`` WITHOUT inserting, so the on-demand news EOD
        cache-first marker advances even when a fetch returns only duplicates
        (``save_if_new`` no-ops on dedup and never refreshes ``fetched_at``).
        Returns False when no such row exists (a ticker that has never had
        news) — the rare case where the next request still re-fetches."""

        stmt = (
            select(News)
            .where(News.ticker == ticker, News.source == source)
            .order_by(News.fetched_at.desc())
            .limit(1)
        )
        row = self._session.execute(stmt).scalar_one_or_none()
        if row is None:
            return False
        row.fetched_at = fetched_at
        self._session.flush()
        return True

    def latest_fetched_at_for_ticker(
        self, ticker: str, *, source: str | None = None
    ) -> datetime | None:
        """B064 F002 — the most recent ``fetched_at`` for ``ticker`` (optionally
        scoped to ``source``), or None when no row exists.

        Backs the on-demand CN/HK news ingest's EOD cache-first check: the
        request path re-fetches a symbol's eastmoney news at most once per UTC
        day, so a same-day ``fetched_at`` means the lookup serves the already-
        ingested rows instead of re-hitting akshare."""

        stmt = select(News.fetched_at).where(News.ticker == ticker)
        if source is not None:
            stmt = stmt.where(News.source == source)
        stmt = stmt.order_by(News.fetched_at.desc()).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()

    def list_by_ticker(
        self,
        ticker: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[News]:
        stmt = select(News).where(News.ticker == ticker)
        if since is not None:
            stmt = stmt.where(News.published_at >= since)
        stmt = stmt.order_by(News.published_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def list_by_source(
        self,
        source: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[News]:
        stmt = select(News).where(News.source == source)
        if since is not None:
            stmt = stmt.where(News.published_at >= since)
        stmt = stmt.order_by(News.published_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def list_latest_global(
        self,
        *,
        limit: int = 20,
        since: datetime | None = None,
        source: str | None = None,
        form_type: str | None = None,
    ) -> list[News]:
        """B038 F001 — newest-first global feed across all tickers.

        Unlike :meth:`list_by_ticker` / :meth:`list_by_source` this applies
        no ticker scoping — it backs the Home "Today's market news" section
        (``GET /api/news/latest``), which shows the freshest market-wide
        headlines regardless of sleeve / ticker. Optional ``source`` /
        ``form_type`` / ``since`` filters narrow the feed; all are ANDed.
        """

        stmt = select(News)
        if since is not None:
            stmt = stmt.where(News.published_at >= since)
        if source is not None:
            stmt = stmt.where(News.source == source)
        if form_type is not None:
            stmt = stmt.where(News.form_type == form_type)
        stmt = stmt.order_by(News.published_at.desc()).limit(limit)
        return list(self._session.execute(stmt).scalars().all())

    def list_untranslated(self, *, limit: int = 500) -> list[News]:
        """B054 F-news — rows whose ``title_zh`` is still NULL, newest-first.

        Backs the ``news_translation`` batch job (off the request path): it
        fetches the headlines that have not yet been translated to Simplified
        Chinese, translates them via the LLM gateway, and writes ``title_zh``.
        Idempotent by construction — a row already carrying a ``title_zh`` is
        skipped on the next run, so re-running the job only spends budget on
        genuinely-new headlines (B043 idempotency lesson: a real translated
        value, never a placeholder, gates the skip).
        """

        stmt = (
            select(News)
            .where(News.title_zh.is_(None))
            .order_by(News.published_at.desc())
            .limit(limit)
        )
        return list(self._session.execute(stmt).scalars().all())

    def list_all_rows(self) -> Sequence[News]:
        """Type-friendly alias around :meth:`list_all` for code that wants
        a ``Sequence[News]`` annotation rather than ``list[News]``.
        """

        return self.list_all()
