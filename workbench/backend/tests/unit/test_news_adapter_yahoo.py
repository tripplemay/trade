"""B033 F003 — YahooRSSNewsAdapter fixture round-trip + since filter +
non-200 guard + per-entry snapshot fragment + repository persistence.

Adapter is tested via a fake HTTP client (the ``_HttpClient`` Protocol);
the fake serves the bundled ``data/fixtures/news/yahoo-sample-*.xml``
feeds for the headline RSS call. No real network access — fixture-first
per the spec's CI strategy. ``feedparser`` runs for real against the
fixture bytes so the test exercises the same parse path production uses.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import feedparser  # type: ignore[import-untyped]
import pytest

from workbench_api.news.adapters.yahoo_rss import (
    YAHOO_RSS_BASE_URL,
    YahooRSSNewsAdapter,
    snapshot_filename,
)
from workbench_api.news.snapshot import NewsSnapshotWriter

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_DIR = REPO_ROOT / "data" / "fixtures" / "news"


def _load_fixture(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


@dataclass
class _FakeResponse:
    """Minimal subset of :class:`httpx.Response` the adapter reads."""

    status_code: int = 200
    _body: bytes = b""

    @property
    def content(self) -> bytes:
        return self._body


class _FakeClient:
    """Returns a single canned body for any GET + records the URLs hit."""

    def __init__(self, *, body: bytes, status_code: int = 200) -> None:
        self._body = body
        self._status = status_code
        self.requests: list[str] = []

    def get(self, url: str) -> _FakeResponse:
        self.requests.append(url)
        return _FakeResponse(status_code=self._status, _body=self._body)


def test_fetch_parses_aapl_feed_into_news_items() -> None:
    """All three AAPL fixture items map to NewsItem rows with the
    Yahoo-source fields filled in (form_type stays None — RSS has no
    SEC form concept)."""

    client = _FakeClient(body=_load_fixture("yahoo-sample-AAPL.xml"))
    adapter = YahooRSSNewsAdapter(client=client)
    items = list(
        adapter.fetch(ticker="AAPL", since=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert len(items) == 3
    first = next(i for i in items if i.source_id == "aapl-q2-2026-001")
    assert first.source == "yahoo_rss"
    assert first.ticker == "AAPL"
    assert first.form_type is None
    assert first.raw_ext == "xml"
    assert first.title == "Apple Reports Q2 Earnings Above Estimates"
    assert first.url == "https://finance.yahoo.com/news/apple-q2-earnings-2026"
    assert first.summary is not None and "consensus EPS" in first.summary
    assert first.published_at == datetime(2026, 5, 11, 12, 0, 0, tzinfo=UTC)


def test_fetch_url_carries_ticker_region_and_lang() -> None:
    """The request URL must hit the pinned endpoint with the ticker +
    US/en query params (so a Yahoo endpoint drift fails loud)."""

    client = _FakeClient(body=_load_fixture("yahoo-sample-SPY.xml"))
    adapter = YahooRSSNewsAdapter(client=client)
    list(adapter.fetch(ticker="SPY", since=datetime(2026, 1, 1, tzinfo=UTC)))
    assert len(client.requests) == 1
    url = client.requests[0]
    assert url.startswith(YAHOO_RSS_BASE_URL)
    assert "s=SPY" in url
    assert "region=US" in url
    assert "lang=en-US" in url


def test_fetch_since_filter_excludes_older_entries() -> None:
    """``since`` is an inclusive lower bound on ``published_at``. The
    May 11 AAPL item drops when ``since`` is May 12; May 12 + May 13
    survive."""

    client = _FakeClient(body=_load_fixture("yahoo-sample-AAPL.xml"))
    adapter = YahooRSSNewsAdapter(client=client)
    items = list(
        adapter.fetch(ticker="AAPL", since=datetime(2026, 5, 12, tzinfo=UTC))
    )
    source_ids = {i.source_id for i in items}
    assert "aapl-q2-2026-001" not in source_ids  # 2026-05-11, before since
    assert source_ids == {"aapl-iphone-18-launch", "aapl-dividend-q2-2026"}
    assert all(i.published_at >= datetime(2026, 5, 12, tzinfo=UTC) for i in items)


def test_fetch_spy_fixture_yields_two_items() -> None:
    client = _FakeClient(body=_load_fixture("yahoo-sample-SPY.xml"))
    adapter = YahooRSSNewsAdapter(client=client)
    items = list(
        adapter.fetch(ticker="SPY", since=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert len(items) == 2
    assert {i.ticker for i in items} == {"SPY"}


def test_fetch_non_200_raises_loud() -> None:
    """A 4xx/5xx from Yahoo must raise rather than silently return an
    empty feed — an operator running the CLI should see the failure."""

    client = _FakeClient(body=b"", status_code=503)
    adapter = YahooRSSNewsAdapter(client=client)
    with pytest.raises(RuntimeError, match="status 503"):
        list(adapter.fetch(ticker="AAPL", since=datetime(2026, 1, 1, tzinfo=UTC)))


def test_fetch_skips_entry_without_pubdate() -> None:
    """An item with no ``<pubDate>`` is skipped (it cannot satisfy the
    ``published_at`` NOT NULL contract); items with one survive."""

    feed = (
        b'<?xml version="1.0" encoding="UTF-8"?>\n'
        b'<rss version="2.0"><channel>\n'
        b"<item><title>No date headline</title>"
        b"<link>https://finance.yahoo.com/news/no-date</link>"
        b'<guid isPermaLink="false">no-date-001</guid></item>\n'
        b"<item><title>Dated headline</title>"
        b"<link>https://finance.yahoo.com/news/dated</link>"
        b'<guid isPermaLink="false">dated-001</guid>'
        b"<pubDate>Mon, 11 May 2026 12:00:00 GMT</pubDate></item>\n"
        b"</channel></rss>\n"
    )
    client = _FakeClient(body=feed)
    adapter = YahooRSSNewsAdapter(client=client)
    items = list(
        adapter.fetch(ticker="AAPL", since=datetime(2026, 1, 1, tzinfo=UTC))
    )
    assert [i.source_id for i in items] == ["dated-001"]


def test_snapshot_filename_is_deterministic_16_hex() -> None:
    """The snapshot stem is ``sha256(guid)[:16]`` — stable across runs so
    a re-fetch overwrites the same file rather than duplicating it."""

    guid = "aapl-q2-2026-001"
    stem = snapshot_filename(guid)
    assert stem == hashlib.sha256(guid.encode("utf-8")).hexdigest()[:16]
    assert len(stem) == 16
    assert snapshot_filename(guid) == stem  # deterministic


def test_raw_body_is_self_contained_xml_fragment() -> None:
    """Each row's raw body is a standalone ``<item>`` document containing
    the entry's identifying fields — re-parseable without the full feed
    and deterministic for ``content_sha256``."""

    client = _FakeClient(body=_load_fixture("yahoo-sample-AAPL.xml"))
    adapter = YahooRSSNewsAdapter(client=client)
    item = next(
        i
        for i in adapter.fetch(ticker="AAPL", since=datetime(2026, 1, 1, tzinfo=UTC))
        if i.source_id == "aapl-iphone-18-launch"
    )
    assert item.raw_body.startswith(b"<?xml")
    assert b"aapl-iphone-18-launch" in item.raw_body
    # Round-trips back through feedparser without error.
    reparsed = feedparser.parse(item.raw_body)
    assert reparsed.entries[0].get("id") == "aapl-iphone-18-launch"


def test_fetch_writes_snapshot_and_persists_via_repository(
    initialised_db: str,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """End-to-end: adapter → NewsSnapshotWriter → NewsRepository, the
    exact composition the F003 CLI runs. Snapshot lands at the
    partitioned yahoo_rss path and the row references it + the sha256."""

    from sqlalchemy.orm import sessionmaker

    from workbench_api.db.engine import get_engine
    from workbench_api.db.repositories.news import NewsRepository

    client = _FakeClient(body=_load_fixture("yahoo-sample-SPY.xml"))
    adapter = YahooRSSNewsAdapter(client=client)
    snapshot_root = tmp_path / "snapshots"
    writer = NewsSnapshotWriter(snapshot_root)
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        repo = NewsRepository(session)
        item = next(
            iter(adapter.fetch(ticker="SPY", since=datetime(2026, 1, 1, tzinfo=UTC)))
        )
        stem = snapshot_filename(item.source_id)
        snap = writer.write(
            source=item.source,
            published_on=item.published_at.date(),
            identifier=stem,
            body=item.raw_body,
            ext=item.raw_ext,
        )
        row = repo.save_if_new(
            item,
            snapshot_path=snap.relative_path,
            content_sha256=snap.content_sha256,
        )
        assert row is not None
        assert row.source == "yahoo_rss"
        assert row.snapshot_path == snap.relative_path
        assert row.snapshot_path.startswith("yahoo_rss/")
        assert row.snapshot_path.endswith(f"{stem}.xml")
        assert row.content_sha256 == hashlib.sha256(item.raw_body).hexdigest()
        on_disk = snapshot_root / snap.relative_path
        assert on_disk.is_file()
        assert on_disk.read_bytes() == item.raw_body
    finally:
        session.close()
