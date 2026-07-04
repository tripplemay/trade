"""B080 F004 fix ② — cn_attack paper accounts base_currency USD → CNY.

Data-only: forward-fix any already-activated cn_attack paper account to CNY (the
A-share modes trade CNY-denominated names). Master / regime accounts are untouched
(their strategy_ids are not in the WHERE clause) — zero regression. A no-op when no
cn_attack paper account exists yet (the common case: paper accounts are activated on
demand, never bootstrap-seeded).

Revision ID: 0032_b080_cn_attack_paper_cny
Revises: 0031_b080_reverify_job
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0032_b080_cn_attack_paper_cny"
down_revision: str | Sequence[str] | None = "0031_b080_reverify_job"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE paper_account SET base_currency = 'CNY' "
        "WHERE strategy_id IN ('cn_attack_pure_momentum', 'cn_attack_quality_momentum')"
    )


def downgrade() -> None:
    op.execute(
        "UPDATE paper_account SET base_currency = 'USD' "
        "WHERE strategy_id IN ('cn_attack_pure_momentum', 'cn_attack_quality_momentum')"
    )
