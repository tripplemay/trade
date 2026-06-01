"""B034 F001 — NewsEmbedding model + repository + alembic 0006.

Exercises every operation the F001 embedder and the F002 association
service call against the ``news_embedding`` table. Mirrors the layout
of :mod:`tests.unit.test_news_repository` (B033 F001) so a maintainer
reading both can swap one for the other in their head.

All sessions opened here are closed before the per-test teardown so the
SQLite file DB is never locked when ``initialised_db`` drops the schema.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.models.news_embedding import NewsEmbedding
from workbench_api.db.repositories.news import NewsRepository
from workbench_api.db.repositories.news_embedding import NewsEmbeddingRepository
from workbench_api.news.adapters.base import NewsItem


def _news_item(source_id: str = "0000320193-26-000001") -> NewsItem:
    return NewsItem(
        source="sec_edgar",
        source_id=source_id,
        url="https://www.sec.gov/x",
        title="Apple Inc. — 10-K (2026)",
        summary="Annual report",
        ticker="AAPL",
        form_type="10-K",
        published_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
        raw_body=b"<html>body</html>",
        raw_ext="htm",
    )


@pytest.fixture
def ctx(initialised_db: str) -> Iterator[SimpleNamespace]:  # noqa: ARG001
    """One shared session + one seeded news row + an embedding repo.

    Closing the session in teardown (before ``initialised_db`` drops the
    schema) keeps the SQLite file unlocked."""

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session: Session = factory()
    news = NewsRepository(session).save_if_new(
        _news_item(),
        snapshot_path="sec_edgar/2026-05-01/0000320193-26-000001.htm",
        content_sha256="aa" * 32,
    )
    assert news is not None
    session.commit()
    yield SimpleNamespace(
        news_id=news.id,
        session=session,
        factory=factory,
        repo=NewsEmbeddingRepository(session),
    )
    session.close()


def test_save_if_new_inserts_first_row(ctx: SimpleNamespace) -> None:
    row = ctx.repo.save_if_new(
        news_id=ctx.news_id,
        model="bge-m3",
        vector=[0.1, 0.2, 0.3],
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert row is not None
    assert row.news_id == ctx.news_id
    assert row.model == "bge-m3"
    assert row.dim == 3
    assert row.vector == [0.1, 0.2, 0.3]
    assert ctx.repo.count() == 1


def test_save_if_new_is_idempotent_by_news_and_model(ctx: SimpleNamespace) -> None:
    first = ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[1.0, 0.0])
    second = ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[0.0, 1.0])
    assert first is not None
    assert second is None
    assert ctx.repo.count() == 1


def test_save_if_new_allows_same_news_different_model(ctx: SimpleNamespace) -> None:
    """The unique key is ``(news_id, model)`` so re-embedding the same
    news under a different model is a fresh row, not a dup."""

    ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[1.0, 0.0])
    other = ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-large", vector=[0.0, 1.0])
    assert other is not None
    assert ctx.repo.count() == 2


def test_save_if_new_derives_dim_from_vector_length(ctx: SimpleNamespace) -> None:
    row = ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[0.0] * 1024)
    assert row is not None
    assert row.dim == 1024


def test_get_by_news_and_model_round_trip(ctx: SimpleNamespace) -> None:
    ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[0.5, 0.5])
    found = ctx.repo.get_by_news_and_model(ctx.news_id, "bge-m3")
    assert found is not None
    assert found.vector == [0.5, 0.5]
    assert ctx.repo.get_by_news_and_model(ctx.news_id, "missing-model") is None
    assert ctx.repo.get_by_news_and_model(uuid4(), "bge-m3") is None


def test_list_vectors_by_news_ids_bulk(ctx: SimpleNamespace) -> None:
    # Add a second news row in the same session so the bulk fetch has two.
    second = NewsRepository(ctx.session).save_if_new(
        _news_item(source_id="0000320193-26-000002"),
        snapshot_path="sec_edgar/2026-05-01/0000320193-26-000002.htm",
        content_sha256="bb" * 32,
    )
    assert second is not None
    ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[1.0, 2.0])
    ctx.repo.save_if_new(news_id=second.id, model="bge-m3", vector=[3.0, 4.0])

    out = ctx.repo.list_vectors_by_news_ids([ctx.news_id, second.id], "bge-m3")
    assert out == {ctx.news_id: [1.0, 2.0], second.id: [3.0, 4.0]}


def test_list_vectors_by_news_ids_empty_short_circuits(ctx: SimpleNamespace) -> None:
    assert ctx.repo.list_vectors_by_news_ids([], "bge-m3") == {}


def test_list_vectors_by_news_ids_filters_by_model(ctx: SimpleNamespace) -> None:
    ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[1.0])
    assert ctx.repo.list_vectors_by_news_ids([ctx.news_id], "other") == {}


def test_vector_json_round_trip_list_float(ctx: SimpleNamespace) -> None:
    """The ``vector`` JSON column must round-trip a ``list[float]`` so the
    cosine ranker reads back exactly what the embedder wrote."""

    payload = [0.1234567, -0.7654321, 0.0, 1.0, -1.0]
    ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=payload)
    ctx.session.expire_all()  # force a reload from the DB, not the identity map
    row = ctx.repo.get_by_news_and_model(ctx.news_id, "bge-m3")
    assert row is not None
    assert row.vector == payload


def test_news_embedding_columns_match_schema(ctx: SimpleNamespace) -> None:  # noqa: ARG001
    """Pin the exact column set so a future schema edit can't drift from
    the migration silently."""

    columns = {c["name"] for c in inspect(get_engine()).get_columns("news_embedding")}
    assert columns == {"id", "news_id", "model", "dim", "vector", "created_at"}


def test_fk_declares_cascade_delete() -> None:
    """The ``news_id`` FK must declare ``ON DELETE CASCADE`` so removing a
    news row drops its embeddings. Asserted at the ORM-metadata level
    (portable; SQLite test env does not enforce FKs by default, but
    Postgres production always does)."""

    fks = list(NewsEmbedding.__table__.foreign_keys)
    news_fk = next(fk for fk in fks if fk.column.table.name == "news")
    assert news_fk.parent.name == "news_id"
    assert news_fk.column.name == "id"
    assert (news_fk.ondelete or "").upper() == "CASCADE"


def test_alembic_upgrade_creates_news_embedding_table(tmp_db_url: str) -> None:
    """0006 must materialise ``news_embedding`` + the unique constraint +
    index, and downgrade to 0005 strips it without disturbing ``news`` or
    the earlier baseline."""

    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option(
        "script_location", f"{backend_root}/workbench_api/db/migrations"
    )
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)

    command.upgrade(cfg, "0006_b034_news_embedding")
    inspector = inspect(get_engine())
    assert "news_embedding" in set(inspector.get_table_names())
    columns = {col["name"] for col in inspector.get_columns("news_embedding")}
    assert columns == {"id", "news_id", "model", "dim", "vector", "created_at"}
    indexes = {idx["name"] for idx in inspector.get_indexes("news_embedding")}
    assert "ix_news_embedding_news_id" in indexes
    uniques = {uc["name"] for uc in inspector.get_unique_constraints("news_embedding")}
    assert "uq_news_embedding_news_model" in uniques

    # Downgrade explicitly to 0005 (not "-1") per the B033 F001 lesson.
    command.downgrade(cfg, "0005_b033_news")
    inspector = inspect(get_engine())
    after = set(inspector.get_table_names())
    assert "news_embedding" not in after
    assert "news" in after  # B033 table survives the B034 downgrade.


def test_unique_constraint_blocks_duplicate_via_orm(ctx: SimpleNamespace) -> None:
    """save_if_new guards the happy path; the DB-level unique constraint
    must still block a stray duplicate that bypasses the repository."""

    from sqlalchemy.exc import IntegrityError

    ctx.repo.save_if_new(news_id=ctx.news_id, model="bge-m3", vector=[1.0])
    duplicate = NewsEmbedding(
        id=uuid4(),
        news_id=ctx.news_id,
        model="bge-m3",  # same (news_id, model)
        dim=1,
        vector=[2.0],
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    ctx.session.add(duplicate)
    with pytest.raises(IntegrityError):
        ctx.session.flush()
    ctx.session.rollback()
