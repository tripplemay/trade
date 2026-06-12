"""B058 F001 — paper_account.build_complete (stuck-in-cash retry sentinel).

Adds ``paper_account.build_complete`` (Boolean, NOT NULL, server_default ``1``).
It marks whether the account's ``target_key`` allocation is FULLY built (every
markable target symbol bought, no skips). A degraded build — a target symbol
lacked a price mark at rebalance time — sets this False so the daily MTM job
keeps retrying until the mark arrives and the book is built, instead of locking
the account all-cash forever (the S2 bug: ``target_key`` was committed even on
an all-cash no-op, and the daily job — keyed only on a target_key *change* —
then never retried).

Existing rows backfill to ``True`` (assumed built under the old logic); a known
stuck account is healed on demand via the B058 F004 "align to current target"
primitive, not by silent daily forced alignment (spec §3: alignment is
open/on-demand only, never a daily forced rebalance).

Revision ID: 0022_b058_paper_build_complete
Revises: 0021_b057_execution_strategy_id
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022_b058_paper_build_complete"
down_revision: str | Sequence[str] | None = "0021_b057_execution_strategy_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("paper_account", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "build_complete",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("1"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("paper_account", schema=None) as batch_op:
        batch_op.drop_column("build_complete")
