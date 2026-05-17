"""Schemas for the snapshots endpoints (F011)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SnapshotSummary(BaseModel):
    """Row in the snapshots list view."""

    id: str = Field(description="SnapshotMeta primary key (matches DB row).")
    as_of_date: str = Field(description="ISO-8601 date the snapshot represents.")
    created_at: str = Field(description="ISO-8601 timestamp the file landed on disk.")
    quality_status: str = Field(description="'ok' / 'stale' / 'missing'.")
    file_path: str


class SnapshotListResponse(BaseModel):
    snapshots: list[SnapshotSummary]


class SnapshotRefreshResponse(BaseModel):
    """POST /api/snapshots/refresh acknowledgement (SSE streams progress)."""

    job_id: str
    status: str = Field(description="'started' / 'failed_to_start'.")
    detail: str | None = None
