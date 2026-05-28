"""B033 F001 — NewsSnapshotWriter file IO + sha256 + mkdir -p."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

import pytest

from workbench_api.news.snapshot import NewsSnapshotWriter


def test_writer_writes_body_to_partitioned_path(tmp_path: Path) -> None:
    writer = NewsSnapshotWriter(tmp_path)
    body = b"<html>10-K body</html>"
    result = writer.write(
        source="sec_edgar",
        published_on=date(2026, 5, 1),
        identifier="0000320193-26-000001",
        body=body,
        ext="htm",
    )
    expected_relative = "sec_edgar/2026-05-01/0000320193-26-000001.htm"
    assert result.relative_path == expected_relative
    assert result.absolute_path == tmp_path / expected_relative
    assert result.absolute_path.read_bytes() == body


def test_writer_computes_sha256_of_body(tmp_path: Path) -> None:
    writer = NewsSnapshotWriter(tmp_path)
    body = b"<?xml version='1.0'?><rss/>"
    result = writer.write(
        source="yahoo_rss",
        published_on=date(2026, 5, 1),
        identifier="abcdef0123456789",
        body=body,
        ext="xml",
    )
    assert result.content_sha256 == hashlib.sha256(body).hexdigest()


def test_writer_creates_missing_directories(tmp_path: Path) -> None:
    """mkdir -p: the source / day directories must be auto-created."""

    root = tmp_path / "nested" / "snapshots"  # also missing
    assert not root.exists()
    writer = NewsSnapshotWriter(root)
    writer.write(
        source="sec_edgar",
        published_on=date(2026, 4, 30),
        identifier="x",
        body=b"hi",
        ext="htm",
    )
    assert (root / "sec_edgar" / "2026-04-30" / "x.htm").is_file()


def test_writer_overwrites_existing_file_with_same_identifier(tmp_path: Path) -> None:
    """A re-fetch with drifted body should overwrite on disk; the
    repository layer is what de-duplicates by ``(source, source_id)``.
    The writer stays content-addressed: the new sha256 reflects the new
    body so a divergent re-fetch is detectable."""

    writer = NewsSnapshotWriter(tmp_path)
    first = writer.write(
        source="sec_edgar",
        published_on=date(2026, 5, 1),
        identifier="acc-1",
        body=b"v1",
        ext="htm",
    )
    second = writer.write(
        source="sec_edgar",
        published_on=date(2026, 5, 1),
        identifier="acc-1",
        body=b"v2",
        ext="htm",
    )
    assert first.relative_path == second.relative_path
    assert first.content_sha256 != second.content_sha256
    assert (tmp_path / first.relative_path).read_bytes() == b"v2"


def test_writer_strips_leading_dot_from_ext(tmp_path: Path) -> None:
    writer = NewsSnapshotWriter(tmp_path)
    result = writer.write(
        source="sec_edgar",
        published_on=date(2026, 5, 1),
        identifier="acc",
        body=b"x",
        ext=".xml",
    )
    assert result.relative_path.endswith("/acc.xml")


def test_writer_rejects_empty_source_and_identifier(tmp_path: Path) -> None:
    writer = NewsSnapshotWriter(tmp_path)
    with pytest.raises(ValueError):
        writer.write(
            source="",
            published_on=date(2026, 5, 1),
            identifier="acc",
            body=b"x",
            ext="htm",
        )
    with pytest.raises(ValueError):
        writer.write(
            source="sec_edgar",
            published_on=date(2026, 5, 1),
            identifier="",
            body=b"x",
            ext="htm",
        )
    with pytest.raises(ValueError):
        writer.write(
            source="sec_edgar",
            published_on=date(2026, 5, 1),
            identifier="acc",
            body=b"x",
            ext="",
        )
