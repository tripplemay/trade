"""SnapshotMeta model — registry of public data snapshots.

The actual snapshot payloads remain on disk under ``data/public-cache/`` per
B009; this row is the catalog entry the workbench renders in the Snapshots
page (B022). ``quality_status`` is a free-form short label ("ok",
"degraded:gap", etc.) the snapshot pipeline emits; the database is not the
authority on quality grading.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class SnapshotMeta(Base):
    __tablename__ = "snapshot_meta"

    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    manifest_path: Mapped[str] = mapped_column(String(255), nullable=False)
    quality_status: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"SnapshotMeta(snapshot_id={self.snapshot_id!r}, status={self.quality_status!r})"
