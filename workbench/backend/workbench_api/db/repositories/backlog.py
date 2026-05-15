"""BacklogRepository — mirror of `backlog.json`."""

from __future__ import annotations

from workbench_api.db.models.backlog_entry import BacklogEntry
from workbench_api.db.repositories.base import Repository


class BacklogRepository(Repository[BacklogEntry, str]):
    model = BacklogEntry
    primary_key_attr = "id"
