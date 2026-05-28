"""B033 F001 — NewsSnapshotWriter.

Writes raw news / filing body to ``data/snapshots/news/{source}/{YYYY-MM-DD}/``
and returns (relative path, sha256 hex). The path is what
``News.snapshot_path`` stores; the sha256 backs ``News.content_sha256``
so a future re-fetch can detect upstream content drift without keeping
the body in DB (permanent product boundary **(p)**).

The writer is intentionally tiny — it does file I/O and hashing,
nothing else. Adapters own URL fetching + rate limiting + dedup; the
repository owns DB persistence. Each layer stays single-purpose so
the F002 / F003 adapters can be unit-tested against a writable
``tmp_path`` without standing up a fake HTTP server.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SnapshotResult:
    """Outcome of writing one raw body to disk."""

    relative_path: str
    content_sha256: str
    absolute_path: Path


class NewsSnapshotWriter:
    """Persist raw news / filing bodies under ``root/{source}/{YYYY-MM-DD}/``.

    ``root`` defaults to ``data/snapshots/news`` relative to the project
    root. Callers pass an absolute :class:`Path` so production CLI and
    pytest can both pick their own location.
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def write(
        self,
        *,
        source: str,
        published_on: date,
        identifier: str,
        body: bytes,
        ext: str,
    ) -> SnapshotResult:
        """Write ``body`` to ``{root}/{source}/{YYYY-MM-DD}/{identifier}.{ext}``.

        The destination directory is created if absent (mkdir -p). The
        returned ``relative_path`` is rooted at the snapshot root —
        ``{source}/{YYYY-MM-DD}/{identifier}.{ext}`` — so callers can
        store the same string regardless of the writer's absolute root.
        ``content_sha256`` is the hex digest of ``body`` exactly as
        written; matching the file on disk byte-for-byte detects upstream
        drift on a re-fetch.
        """

        if not source:
            raise ValueError("source must be a non-empty string")
        if not identifier:
            raise ValueError("identifier must be a non-empty string")
        clean_ext = ext.lstrip(".")
        if not clean_ext:
            raise ValueError("ext must be a non-empty string")

        day_dir = self._root / source / published_on.isoformat()
        day_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{identifier}.{clean_ext}"
        absolute = day_dir / filename
        absolute.write_bytes(body)
        relative = f"{source}/{published_on.isoformat()}/{filename}"
        digest = hashlib.sha256(body).hexdigest()
        return SnapshotResult(
            relative_path=relative,
            content_sha256=digest,
            absolute_path=absolute,
        )
