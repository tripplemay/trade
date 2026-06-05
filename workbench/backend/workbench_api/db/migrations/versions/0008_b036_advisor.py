"""B036 F001 — advisor_recommendation table.

Adds the ``advisor_recommendation`` table storing the AI advisor's
per-sleeve structured output (advice JSON + citation set + status). The
daily precompute writes here; ``GET /advisor`` reads the latest per sleeve.

Revision ID: 0008_b036_advisor
Revises: 0007_b035_market_context
Create Date: 2026-06-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_b036_advisor"
down_revision: str | Sequence[str] | None = "0007_b035_market_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "advisor_recommendation",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("sleeve", sa.String(length=64), nullable=False),
        sa.Column("advice_json", sa.JSON(), nullable=False),
        sa.Column("quant_signal_sha", sa.Text(), nullable=False),
        sa.Column("references_json", sa.JSON(), nullable=False),
        sa.Column("model", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_advisor_recommendation_sleeve", "advisor_recommendation", ["sleeve"]
    )
    op.create_index(
        "ix_advisor_recommendation_generated_at",
        "advisor_recommendation",
        ["generated_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_advisor_recommendation_generated_at", table_name="advisor_recommendation"
    )
    op.drop_index(
        "ix_advisor_recommendation_sleeve", table_name="advisor_recommendation"
    )
    op.drop_table("advisor_recommendation")
