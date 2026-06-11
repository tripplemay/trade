"""B033 permanent product boundary **(p)** — news schema is metadata-only.

The ``news`` table stores **only metadata + snapshot path**. Raw
filing / article body lands on disk under
``data/snapshots/news/{source}/{YYYY-MM-DD}/`` and is referenced by
``snapshot_path`` + ``content_sha256``.

A future migration that adds a ``raw_text`` / ``body`` / ``content``
TEXT column would explode the row size and bypass the snapshot writer
hash contract. This guard reads ``News.__table__`` and asserts no such
column exists. Adding one must go through a permanent-boundary
relaxation note (see ``framework/proposed-learnings.md``) and an
explicit edit to this test.
"""

from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.types import JSON

from workbench_api.db.models.news import News
from workbench_api.db.models.news_embedding import NewsEmbedding

_BLOCKED_BODY_COLUMNS: frozenset[str] = frozenset({"raw_text", "body", "content"})


def test_news_table_has_no_raw_body_text_column() -> None:
    text_body_columns = {
        col.name
        for col in News.__table__.columns
        if isinstance(col.type, Text) and col.name in _BLOCKED_BODY_COLUMNS
    }
    assert not text_body_columns, (
        "Permanent product boundary (p) violated: news table grew a raw "
        f"body TEXT column ({sorted(text_body_columns)}). Raw filing / "
        "article body must live under data/snapshots/news/ — only the "
        "path and sha256 belong in DB. Edit the boundary in "
        "framework/proposed-learnings.md before relaxing this guard."
    )


def test_news_table_column_set_is_metadata_only() -> None:
    """Pin the exact column set so a future schema edit can't silently
    smuggle a ``raw_text`` / ``body`` / ``content`` column in under a
    different type (e.g. ``LargeBinary``)."""

    columns = {col.name for col in News.__table__.columns}
    assert columns == {
        "id",
        "source",
        "source_id",
        "url",
        "title",
        # B054 F-news — Simplified-Chinese headline (LLM translate of `title`,
        # no-AI boundary rule (e)). A localized headline is metadata like
        # `title`, **not** raw article body, so boundary (p) is preserved.
        "title_zh",
        "summary",
        "ticker",
        "form_type",
        "published_at",
        "fetched_at",
        "snapshot_path",
        "content_sha256",
        "ticker_mentions",
    }, (
        "Permanent product boundary (p): news columns drifted from the B033 "
        "spec §4.2 metadata-only schema. Any new column must be reviewed "
        "against the boundary before merge."
    )


def test_news_table_snapshot_path_and_hash_are_required() -> None:
    """A row without ``snapshot_path`` / ``content_sha256`` would mean the
    body lives only in DB — exactly the regression boundary (p) blocks.
    """

    columns = {col.name: col for col in News.__table__.columns}
    assert not columns["snapshot_path"].nullable
    assert not columns["content_sha256"].nullable


def test_news_embedding_table_has_no_raw_body_text_column() -> None:
    """B034 boundary (p) extension: the ``news_embedding`` table holds a
    vector, never raw filing / article body. Block any ``raw_text`` /
    ``body`` / ``content`` TEXT column from sneaking in alongside it."""

    text_body_columns = {
        col.name
        for col in NewsEmbedding.__table__.columns
        if isinstance(col.type, Text) and col.name in _BLOCKED_BODY_COLUMNS
    }
    assert not text_body_columns, (
        "Permanent product boundary (p) violated: news_embedding grew a raw "
        f"body TEXT column ({sorted(text_body_columns)}). Only the dense "
        "vector belongs here — raw bodies live under data/snapshots/news/."
    )


def test_news_embedding_vector_is_numeric_json_not_text() -> None:
    """The ``vector`` column must be a (numeric) JSON column, not a Text
    column — a regression to TEXT would let raw body smuggle in as a string
    and bypass boundary (p)."""

    vector_col = NewsEmbedding.__table__.columns["vector"]
    assert isinstance(vector_col.type, JSON), (
        "news_embedding.vector must stay a JSON column carrying list[float]; "
        f"got {vector_col.type!r}. A Text/String type would let raw article "
        "body live in DB, violating boundary (p)."
    )
    assert not isinstance(vector_col.type, Text)


def test_news_embedding_table_column_set_is_metadata_only() -> None:
    """Pin the exact column set so a future edit can't smuggle a body
    column into news_embedding under a different name."""

    columns = {col.name for col in NewsEmbedding.__table__.columns}
    assert columns == {"id", "news_id", "model", "dim", "vector", "created_at"}, (
        "Permanent product boundary (p): news_embedding columns drifted from "
        "the B034 spec §4.2 schema. Any new column must be reviewed against "
        "the boundary before merge."
    )
