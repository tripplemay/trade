"""B021 F002 — initial workbench schema.

Three tables, each mirroring a repo-root JSON source so the bootstrap CLI
can round-trip rows without translation:

* ``account``         — mirrors ``accounts/me.json`` (research-account state)
* ``backlog_entry``   — mirrors ``backlog.json``
* ``snapshot_meta``   — registry of public snapshots produced by B009+

Revision ID: 0001_initial
Revises: (none — baseline)
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account",
        sa.Column("account_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("cash", sa.Numeric(20, 4), nullable=False),
        sa.Column("equity_value", sa.Numeric(20, 4), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
    )
    op.create_table(
        "backlog_entry",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("decisions", sa.JSON(), nullable=False),
        sa.Column("confirmed_at", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
    )
    op.create_table(
        "snapshot_meta",
        sa.Column("snapshot_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("manifest_path", sa.String(length=255), nullable=False),
        sa.Column("quality_status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("snapshot_meta")
    op.drop_table("backlog_entry")
    op.drop_table("account")
