"""Schemas for the backlog CRUD endpoints (F012)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacklogEntry(BaseModel):
    """One entry in the backlog list."""

    id: str
    title: str
    description: str
    priority: str = Field(description="'high' / 'medium' / 'low'.")
    status: str = Field(description="'open' / 'in_progress' / 'done' / 'parked'.")
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
    status: str | None = None


class BacklogDeleteResponse(BaseModel):
    """DELETE /api/backlog/{id} response."""

    id: str
    deleted: bool
