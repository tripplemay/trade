"""B056 F001 — paper-trading (forward-simulation) tables.

Creates ``paper_account`` (one virtual account per strategy), ``paper_position``
(virtual holdings), and ``paper_rebalance`` (date + cost per virtual rebalance,
the simplified F003 log). Forward-only simulation: a strategy gets virtual
capital, follows its published allocation, rebalances at close + real costs, and
is marked to market daily. No broker, no real money.

Revision ID: 0018_b056_paper_trading
Revises: 0017_b054_news_title_zh
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_b056_paper_trading"
down_revision: str | Sequence[str] | None = "0017_b054_news_title_zh"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "paper_account",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("strategy_id", sa.String(length=64), nullable=False),
        sa.Column("initial_capital", sa.Float(), nullable=False),
        sa.Column("cash", sa.Float(), nullable=False),
        sa.Column("base_currency", sa.String(length=8), nullable=False),
        sa.Column("fee_bps", sa.Float(), nullable=False),
        sa.Column("slippage_bps", sa.Float(), nullable=False),
        sa.Column("activated_on", sa.Date(), nullable=False),
        sa.Column("last_rebalanced_on", sa.Date(), nullable=True),
        sa.Column("target_key", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("strategy_id", name="uq_paper_account_strategy_id"),
    )
    op.create_index(
        "ix_paper_account_strategy_id", "paper_account", ["strategy_id"]
    )
    op.create_table(
        "paper_position",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=16), nullable=False),
        sa.Column("shares", sa.Float(), nullable=False),
        sa.Column("avg_cost", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["paper_account.id"]),
        sa.UniqueConstraint(
            "account_id", "symbol", name="uq_paper_position_account_symbol"
        ),
    )
    op.create_index(
        "ix_paper_position_account_id", "paper_position", ["account_id"]
    )
    op.create_table(
        "paper_rebalance",
        sa.Column("id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=False),
        sa.Column("rebalance_date", sa.Date(), nullable=False),
        sa.Column("cost", sa.Float(), nullable=False),
        sa.Column("target_key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["paper_account.id"]),
    )
    op.create_index(
        "ix_paper_rebalance_account_id", "paper_rebalance", ["account_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_paper_rebalance_account_id", table_name="paper_rebalance")
    op.drop_table("paper_rebalance")
    op.drop_index("ix_paper_position_account_id", table_name="paper_position")
    op.drop_table("paper_position")
    op.drop_index("ix_paper_account_strategy_id", table_name="paper_account")
    op.drop_table("paper_account")
