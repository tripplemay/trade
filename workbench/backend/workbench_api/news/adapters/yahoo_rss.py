"""B033 F003 — Yahoo Finance RSS news adapter.

Fetches the Yahoo Finance headline RSS for a single ticker, parses the
feed via :mod:`feedparser`, and yields :class:`NewsItem` rows.

Endpoint:
``https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US``

Yahoo Finance does not require an API key or a User-Agent header
contract — a plain ``httpx.Client`` GET works. Rate limits in practice
are generous; the workbench still respects ``time.sleep`` between
calls in the CLI driver so a large universe sweep does not hit
upstream too aggressively.

The adapter writes raw bodies as per-entry XML fragments (one file per
RSS item) keyed by ``sha256(guid)[:16]``. The fragment captures the
entry's identifying fields (``guid`` / ``link`` / ``title`` /
``pubDate`` / ``description``) so a future re-process does not need
the original feed XML — each ``news`` row is self-contained.

``feedparser`` ships without type stubs; the module-level import uses
``# type: ignore[import-untyped]`` (B032 ``yaml`` pattern). The
critical-runtime-deps guard (``tests/safety/test_runtime_dependencies_pinned.py``)
ensures the package stays in ``[project].dependencies`` rather than
``[project.optional-dependencies].dev``.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, Protocol
from xml.sax.saxutils import escape

import feedparser  # type: ignore[import-untyped]
import httpx

from workbench_api.news.adapters.base import NewsItem

logger = logging.getLogger(__name__)


YAHOO_RSS_BASE_URL = "https://feeds.finance.yahoo.com/rss/2.0/headline"
"""Pinned RSS endpoint. If Yahoo deprecates this URL the adapter fails
loudly and the operator updates this constant — preferable to a silent
empty-feed return."""


class _HttpClient(Protocol):
    """Subset of :class:`httpx.Client` the adapter uses.

    Tests inject a fake without paying the real ``httpx.Client``
    connection-pool cost; production builds a real client in
    :py:meth:`__init__`.
    """

    def get(self, url: str) -> Any: ...


class YahooRSSNewsAdapter:
    """Yahoo Finance RSS adapter.

    No secret / no API key required. The constructor accepts an
    injectable ``client`` for unit tests; production calls
    :py:meth:`__init__` with no arguments and a default
    :class:`httpx.Client` is built.
    """

    source: str = "yahoo_rss"

    def __init__(self, *, client: _HttpClient | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=30.0,
            headers={
                "User-Agent": "Workbench Trade research-only news ingest",
                "Accept": "application/rss+xml, application/xml, text/xml",
            },
        )

    def fetch(self, *, ticker: str, since: datetime) -> Iterable[NewsItem]:
        """Yield :class:`NewsItem`s published on/after ``since``.

        ``since`` is timezone-aware UTC. Yahoo RSS publishes ``pubDate``
        in RFC 822 format with a timezone abbreviation; ``feedparser``
        decomposes it into a :class:`time.struct_time`. The adapter
        treats that struct as UTC for comparison (Yahoo headlines are
        UTC in practice; minor drift is acceptable for a 30-day default
        window).

        Entries without a ``guid`` or ``pubDate`` are skipped with a
        debug log — those are rare malformed items that would otherwise
        violate the ``news.source_id`` NOT NULL constraint.
        """

        url = f"{YAHOO_RSS_BASE_URL}?s={ticker}&region=US&lang=en-US"
        response = self._client.get(url)
        status = getattr(response, "status_code", 200)
        if status != 200:
            raise RuntimeError(
                f"Yahoo RSS returned status {status} for {ticker} (url={url})"
            )
        body = response.content
        if not isinstance(body, bytes | bytearray):
            raise TypeError(
                f"Yahoo RSS body is not bytes (got {type(body).__name__}); "
                "test fake must populate ``response.content``"
            )
        return self._parse_feed(body=bytes(body), ticker=ticker, since=since)

    @staticmethod
    def _parse_feed(
        *, body: bytes, ticker: str, since: datetime
    ) -> Iterator[NewsItem]:
        parsed = feedparser.parse(body)
        for entry in parsed.entries:
            guid = entry.get("id") or entry.get("link")
            if not guid:
                logger.debug(
                    "yahoo_rss_skip_no_guid", extra={"ticker": ticker}
                )
                continue
            published_struct = entry.get("published_parsed")
            if not published_struct:
                logger.debug(
                    "yahoo_rss_skip_no_pubdate",
                    extra={"ticker": ticker, "guid": guid},
                )
                continue
            published_at = datetime(
                published_struct.tm_year,
                published_struct.tm_mon,
                published_struct.tm_mday,
                published_struct.tm_hour,
                published_struct.tm_min,
                published_struct.tm_sec,
                tzinfo=UTC,
            )
            if published_at < since:
                continue
            raw_body = _entry_xml_fragment(entry, guid)
            title = str(entry.get("title", "")) or f"{ticker} headline"
            summary = entry.get("summary")
            link = str(entry.get("link", ""))
            yield NewsItem(
                source="yahoo_rss",
                source_id=str(guid),
                url=link or YAHOO_RSS_BASE_URL,
                title=title,
                summary=str(summary) if summary else None,
                ticker=ticker,
                form_type=None,
                published_at=published_at,
                raw_body=raw_body,
                raw_ext="xml",
            )


def snapshot_filename(guid: str) -> str:
    """Build the on-disk filename stem for a Yahoo RSS entry.

    The full snapshot path is computed by :class:`NewsSnapshotWriter`
    (the writer prepends ``{source}/{YYYY-MM-DD}/``); this helper
    returns just the ``{sha256(guid)[:16]}`` portion the CLI uses as
    the ``identifier`` argument to ``write()``.
    """

    return hashlib.sha256(guid.encode("utf-8")).hexdigest()[:16]


def _entry_xml_fragment(entry: Any, guid: str) -> bytes:
    """Serialise one RSS ``<item>`` as a standalone XML document.

    The full feed XML contains every entry; storing the whole feed
    against each row would either duplicate bytes or make snapshot
    paths point to a shared file (breaking the one-row-one-file
    invariant). A per-entry fragment keeps each ``news`` row
    self-contained and deterministic for ``content_sha256``.
    """

    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>\n',
        "<item>\n",
        f"  <guid>{escape(str(guid))}</guid>\n",
    ]
    link = entry.get("link")
    if link:
        parts.append(f"  <link>{escape(str(link))}</link>\n")
    title = entry.get("title")
    if title:
        parts.append(f"  <title>{escape(str(title))}</title>\n")
    published = entry.get("published")
    if published:
        parts.append(f"  <pubDate>{escape(str(published))}</pubDate>\n")
    summary = entry.get("summary")
    if summary:
        parts.append(
            f"  <description><![CDATA[{summary}]]></description>\n"
        )
    parts.append("</item>\n")
    return "".join(parts).encode("utf-8")
