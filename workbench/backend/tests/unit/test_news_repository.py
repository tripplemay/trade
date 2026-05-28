"""B033 F001 — NewsRepository CRUD + save_if_new idempotency + alembic.

Exercises every operation the F002 / F003 adapters and the F003 CLI
will call against the ``news`` table. Mirrors the layout of
:mod:`tests.unit.test_llm_budget_log_repo` (B031 F002) so a maintainer
reading both can swap one for the other in their head.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.news.adapters.base import NewsItem


def _item(
    *,
    source: str = "sec_edgar",
    source_id: str = "0000320193-26-000001",
    url: str = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany",
    title: str = "Apple Inc. — 10-K (2026)",
    summary: str | None = "Annual report",
    ticker: str | None = "AAPL",
    form_type: str | None = "10-K",
    published_at: datetime | None = None,
    raw_body: bytes = b"<html>10-K body</html>",
    raw_ext: str = "htm",
) -> NewsItem:
    return NewsItem(
        source=source,
        source_id=source_id,
        url=url,
        title=title,
        summary=summary,
        ticker=ticker,
        form_type=form_type,
        published_at=published_at or datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        raw_body=raw_body,
        raw_ext=raw_ext,
    )


@pytest.fixture
def repo(initialised_db: str) -> Iterator[NewsRepository]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    yield NewsRepository(session)
    session.close()


def test_save_if_new_inserts_first_row(repo: NewsRepository) -> None:
    row = repo.save_if_new(
        _item(),
        snapshot_path="sec_edgar/2026-05-01/0000320193-26-000001.htm",
        content_sha256="deadbeef" * 8,
    )
    assert row is not None
    assert row.source == "sec_edgar"
    assert row.source_id == "0000320193-26-000001"
    assert row.ticker == "AAPL"
    assert row.form_type == "10-K"
    assert row.snapshot_path == "sec_edgar/2026-05-01/0000320193-26-000001.htm"
    assert row.content_sha256 == "deadbeef" * 8
    assert repo.count() == 1


def test_save_if_new_is_idempotent_by_source_and_source_id(
    repo: NewsRepository,
) -> None:
    """Permanent-product-boundary check — adapter retries must not
    duplicate. Same ``(source, source_id)`` returns ``None`` on the
    second call so the caller can log a skip without an exception."""

    first = repo.save_if_new(
        _item(),
        snapshot_path="sec_edgar/2026-05-01/0000320193-26-000001.htm",
        content_sha256="aa" * 32,
    )
    second = repo.save_if_new(
        _item(title="Different title — same accession"),
        snapshot_path="sec_edgar/2026-05-01/0000320193-26-000001.htm",
        content_sha256="aa" * 32,
    )
    assert first is not None
    assert second is None
    assert repo.count() == 1


def test_get_by_source_and_source_id_round_trip(repo: NewsRepository) -> None:
    repo.save_if_new(
        _item(),
        snapshot_path="sec_edgar/2026-05-01/0000320193-26-000001.htm",
        content_sha256="cc" * 32,
    )
    row = repo.get_by_source_and_source_id("sec_edgar", "0000320193-26-000001")
    assert row is not None
    assert row.title == "Apple Inc. — 10-K (2026)"
    missing = repo.get_by_source_and_source_id("sec_edgar", "missing")
    assert missing is None


def test_list_by_ticker_filters_and_orders_newest_first(repo: NewsRepository) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for offset in (0, 1, 2):
        repo.save_if_new(
            _item(
                source_id=f"AAPL-{offset}",
                published_at=base + timedelta(days=offset),
                title=f"Apple item {offset}",
            ),
            snapshot_path=f"sec_edgar/2026-05-0{offset + 1}/AAPL-{offset}.htm",
            content_sha256=f"{offset:02d}" * 32,
        )
    # Different ticker — must not appear in the AAPL listing.
    repo.save_if_new(
        _item(source_id="NVDA-0", ticker="NVDA", title="NVDA 8-K"),
        snapshot_path="sec_edgar/2026-05-01/NVDA-0.htm",
        content_sha256="dd" * 32,
    )
    rows = repo.list_by_ticker("AAPL")
    titles = [r.title for r in rows]
    assert titles == ["Apple item 2", "Apple item 1", "Apple item 0"]


def test_list_by_ticker_applies_since_and_limit(repo: NewsRepository) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    for offset in range(5):
        repo.save_if_new(
            _item(
                source_id=f"AAPL-{offset}",
                published_at=base + timedelta(days=offset),
                title=f"Apple item {offset}",
            ),
            snapshot_path=f"sec_edgar/2026-05/AAPL-{offset}.htm",
            content_sha256=f"{offset:02d}" * 32,
        )
    rows = repo.list_by_ticker(
        "AAPL", since=base + timedelta(days=2), limit=2
    )
    titles = [r.title for r in rows]
    assert titles == ["Apple item 4", "Apple item 3"]


def test_list_by_source_filters_and_supports_since(repo: NewsRepository) -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    repo.save_if_new(
        _item(source="sec_edgar", source_id="A", published_at=base),
        snapshot_path="a",
        content_sha256="a" * 64,
    )
    repo.save_if_new(
        _item(
            source="yahoo_rss",
            source_id="Y-1",
            published_at=base + timedelta(days=1),
            form_type=None,
        ),
        snapshot_path="b",
        content_sha256="b" * 64,
    )
    repo.save_if_new(
        _item(
            source="yahoo_rss",
            source_id="Y-2",
            published_at=base + timedelta(days=3),
            form_type=None,
        ),
        snapshot_path="c",
        content_sha256="c" * 64,
    )
    sec_rows = repo.list_by_source("sec_edgar")
    yahoo_rows = repo.list_by_source("yahoo_rss", since=base + timedelta(days=2))
    assert {r.source_id for r in sec_rows} == {"A"}
    assert [r.source_id for r in yahoo_rows] == ["Y-2"]


def test_save_if_new_persists_nullable_columns(repo: NewsRepository) -> None:
    """Permanent-product-boundary (p) check — ``ticker_mentions`` stays
    ``None`` until B034 fills it; ``summary`` / ``form_type`` accept
    ``None`` because Yahoo RSS items have no form type."""

    row = repo.save_if_new(
        _item(
            source="yahoo_rss",
            source_id="rss-1",
            summary=None,
            form_type=None,
            ticker="SPY",
        ),
        snapshot_path="yahoo_rss/2026-05-01/rss-1.xml",
        content_sha256="ff" * 32,
    )
    assert row is not None
    assert row.summary is None
    assert row.form_type is None
    assert row.ticker_mentions is None


def test_news_table_columns_match_schema(repo: NewsRepository) -> None:
    """Pin the exact column set so a future schema edit cannot drift
    silently from the migration."""

    columns = {c["name"] for c in inspect(get_engine()).get_columns("news")}
    assert columns == {
        "id",
        "source",
        "source_id",
        "url",
        "title",
        "summary",
        "ticker",
        "form_type",
        "published_at",
        "fetched_at",
        "snapshot_path",
        "content_sha256",
        "ticker_mentions",
    }


def test_alembic_upgrade_creates_news_table(tmp_db_url: str) -> None:
    """End-to-end alembic: 0005 must materialise ``news`` + 3 indexes +
    unique constraint, and downgrade strips them without disturbing the
    B021/B023/B027/B031 baseline."""

    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)

    # Pin the upgrade target to this batch's revision rather than ``head``
    # so a future migration above 0005 doesn't trip ``downgrade("-1")``
    # below (B031's pre-B033 test taught this lesson — see commit history).
    command.upgrade(cfg, "0005_b033_news")
    inspector = inspect(get_engine())
    assert "news" in set(inspector.get_table_names())
    columns = {col["name"] for col in inspector.get_columns("news")}
    assert {
        "id",
        "source",
        "source_id",
        "url",
        "title",
        "summary",
        "ticker",
        "form_type",
        "published_at",
        "fetched_at",
        "snapshot_path",
        "content_sha256",
        "ticker_mentions",
    } == columns
    indexes = {idx["name"] for idx in inspector.get_indexes("news")}
    assert {"ix_news_source", "ix_news_ticker", "ix_news_published_at"}.issubset(
        indexes
    )
    unique_constraints = {
        uc["name"] for uc in inspector.get_unique_constraints("news")
    }
    assert "uq_news_source_source_id" in unique_constraints

    # Downgrade to the revision before B033 so we only assert this batch's
    # table is gone; B031's llm_budget_log + earlier baseline stays.
    command.downgrade(cfg, "0004_b031_llm_budget_log")
    inspector = inspect(get_engine())
    after_tables = set(inspector.get_table_names())
    assert "news" not in after_tables
    # All earlier baseline tables remain untouched.
    assert {
        "account",
        "backlog_entry",
        "snapshot_meta",
        "order_ticket",
        "fill_journal_entry",
        "account_snapshot",
        "tiingo_budget_log",
        "llm_budget_log",
    }.issubset(after_tables)


def test_unique_constraint_blocks_duplicate_source_id_via_orm(
    repo: NewsRepository,
) -> None:
    """save_if_new guards the happy path; this test makes sure the DB-level
    constraint still blocks a stray duplicate insert that bypasses the
    repository (e.g. a future raw ORM .add by accident)."""

    from sqlalchemy.exc import IntegrityError

    from workbench_api.db.models.news import News

    repo.save_if_new(
        _item(),
        snapshot_path="sec_edgar/2026-05-01/0000320193-26-000001.htm",
        content_sha256="aa" * 32,
    )
    from uuid import uuid4

    duplicate = News(
        id=uuid4(),
        source="sec_edgar",
        source_id="0000320193-26-000001",  # same accession
        url="https://duplicate",
        title="dup",
        summary=None,
        ticker="AAPL",
        form_type="10-K",
        published_at=datetime(2026, 5, 2, tzinfo=UTC),
        fetched_at=datetime(2026, 5, 2, tzinfo=UTC),
        snapshot_path="x",
        content_sha256="b" * 64,
        ticker_mentions=None,
    )
    repo._session.add(duplicate)  # noqa: SLF001 — intentional bypass for the test
    with pytest.raises(IntegrityError):
        repo._session.flush()  # noqa: SLF001
    repo._session.rollback()  # noqa: SLF001
