"""SnapshotMetaRepository — registry of public data snapshots."""

from __future__ import annotations

from workbench_api.db.models.snapshot_meta import SnapshotMeta
from workbench_api.db.repositories.base import Repository


class SnapshotMetaRepository(Repository[SnapshotMeta, str]):
    model = SnapshotMeta
    primary_key_attr = "snapshot_id"
