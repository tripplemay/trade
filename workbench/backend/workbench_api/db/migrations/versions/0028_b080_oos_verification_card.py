"""B080 F001 — oos_verification_card table + seed the current cn_attack red card.

Creates the DB-ized OOS "red card" store and seeds one row per cn_attack mode
with the CURRENT in-code caveat values. The seed values are built by importing
``CN_ATTACK_RESEARCH_CAVEAT`` directly (never re-typing) so they are guaranteed
byte-identical to the constant the producer falls back to — the U+2212 minus,
U+2014 em-dash, and fullwidth CJK punctuation in those strings make hand-copying
unsafe. A guard test asserts seed == constant.

Revision ID: 0028_b080_oos_verification_card
Revises: 0027_b079_symbol_name
Create Date: 2026-07-03
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from workbench_api.strategy_modes.cn_attack_precompute import CN_ATTACK_RESEARCH_CAVEAT

revision: str = "0028_b080_oos_verification_card"
down_revision: str | Sequence[str] | None = "0027_b079_symbol_name"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The two research-state cn_attack modes that carry the red card (registry.py).
_CN_ATTACK_STRATEGY_IDS = ("cn_attack_quality_momentum", "cn_attack_pure_momentum")
_SEED_STAMP = datetime(2026, 7, 3, 0, 0, tzinfo=UTC)


def upgrade() -> None:
    op.create_table(
        "oos_verification_card",
        sa.Column("strategy_id", sa.String(length=64), primary_key=True, nullable=False),
        sa.Column("validated", sa.Boolean(), nullable=False),
        sa.Column("oos_result", sa.String(length=32), nullable=False),
        sa.Column("oos_cagr_range", sa.String(length=64), nullable=False),
        sa.Column("headline_zh", sa.String(length=512), nullable=False),
        sa.Column("headline_en", sa.String(length=512), nullable=False),
        sa.Column("detail_zh", sa.String(length=512), nullable=False),
        sa.Column("detail_en", sa.String(length=512), nullable=False),
        sa.Column("backtest_ref", sa.String(length=256), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    seed_table = sa.table(
        "oos_verification_card",
        sa.column("strategy_id", sa.String),
        sa.column("validated", sa.Boolean),
        sa.column("oos_result", sa.String),
        sa.column("oos_cagr_range", sa.String),
        sa.column("headline_zh", sa.String),
        sa.column("headline_en", sa.String),
        sa.column("detail_zh", sa.String),
        sa.column("detail_en", sa.String),
        sa.column("backtest_ref", sa.String),
        sa.column("source", sa.String),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(
        seed_table,
        [
            {
                "strategy_id": strategy_id,
                **CN_ATTACK_RESEARCH_CAVEAT,
                "source": "seed",
                "updated_at": _SEED_STAMP,
            }
            for strategy_id in _CN_ATTACK_STRATEGY_IDS
        ],
    )


def downgrade() -> None:
    op.drop_table("oos_verification_card")
