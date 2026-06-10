"""Schemas for the backlog CRUD endpoints (F012)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacklogEntry(BaseModel):
    """One entry in the backlog list.

    B053 F003 — the ``status`` field was removed: it was never stored (the model
    has no status column), the read path hard-coded it to ``"open"``, and the
    PATCH ``status`` was silently dropped. Rather than wire a column for an
    internal tool page, the phantom field is removed (plumbed-but-ignored
    anti-pattern, framework §17). Re-add a real column + migration if status
    tracking is ever actually needed.
    """

    id: str
    title: str
    description: str
    priority: str = Field(description="'high' / 'medium' / 'low'.")
    created_at: str = Field(description="ISO-8601 timestamp.")
    updated_at: str = Field(description="ISO-8601 timestamp.")


class BacklogListResponse(BaseModel):
    entries: list[BacklogEntry]


class BacklogCreateRequest(BaseModel):
    """POST /api/backlog body."""

    title: str = Field(min_length=1)
    description: str = Field(default="")
    priority: str = Field(default="medium")


class BacklogUpdateRequest(BaseModel):
    """PATCH /api/backlog/{id} body — all fields optional for partial update."""

    title: str | None = None
    description: str | None = None
    priority: str | None = None


class BacklogDeleteResponse(BaseModel):
    """DELETE /api/backlog/{id} response."""

    id: str
    deleted: bool
