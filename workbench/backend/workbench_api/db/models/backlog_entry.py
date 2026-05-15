"""BacklogEntry model — mirrors `backlog.json` at the repo root.

The repo-root `backlog.json` stays the durable source of truth across
sessions; this table is the run-time mirror that workbench pages query.
``decisions`` is stored as JSON (SQLite ``JSON`` type) to keep round-tripping
identical to the source file. ``confirmed_at`` is captured as the original
ISO date string rather than a Python ``date`` because the JSON file
sometimes carries free-form values like ``2026-05-15`` or ``2026-05-15T12:00``.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class BacklogEntry(Base):
    __tablename__ = "backlog_entry"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    decisions: Mapped[list[Any]] = mapped_column(JSON, nullable=False, default=list)
    confirmed_at: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"BacklogEntry(id={self.id!r}, priority={self.priority!r})"
