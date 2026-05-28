"""B033 F001 — NewsAdapter Protocol + NewsItem DTO.

Every news source adapter implements :class:`NewsAdapter`:

- ``source`` (class attribute) — short identifier persisted on
  ``News.source`` (``"sec_edgar"`` / ``"yahoo_rss"``).
- ``fetch(ticker, since)`` — yields :class:`NewsItem` rows ready for
  ``NewsRepository.save_if_new``.

:class:`NewsItem` is an immutable dataclass — adapters build new
instances rather than mutating shared state, so the CLI can iterate
adapter outputs without worrying about cross-thread or cross-adapter
side effects.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class NewsItem:
    """One row of source data on its way to the ``news`` table.

    ``raw_body`` + ``raw_ext`` are handed to
    :class:`workbench_api.news.snapshot.NewsSnapshotWriter` to land on
    disk; the writer returns the relative path + sha256 that the
    repository persists alongside the metadata fields.
    """

    source: str
    source_id: str
    url: str
    title: str
    summary: str | None
    ticker: str | None
    form_type: str | None
    published_at: datetime
    raw_body: bytes
    raw_ext: str


class NewsAdapter(Protocol):
    """Source-specific fetcher contract.

    Implementations stay thin — fetch from upstream, build
    :class:`NewsItem` instances, yield. They do not persist or hash;
    that is the snapshot writer + repository's job, so a test can
    exercise an adapter against an in-memory fake without touching
    the DB or filesystem.
    """

    source: str

    def fetch(self, *, ticker: str, since: datetime) -> Iterable[NewsItem]:
        """Yield :class:`NewsItem`s for ``ticker`` published since ``since``."""
        ...
