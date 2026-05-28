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

from workbench_api.db.models.news import News

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
