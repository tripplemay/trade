"""B082 F002 — seed the 红利低波 OOS card + the 6 backtest trials.

Lands the two DB seeds F002 owns, the SAME auto-on-deploy way B080/B081 did (the deploy
chain runs ``alembic upgrade`` but never the bootstrap CLI), importing the single source
of truth so the migration + the bootstrap CLI converge byte-identically:

1. ``oos_verification_card`` gets one NEW row for ``cn_dividend_lowvol`` seeded from
   ``CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT`` (``validated=False``, ``oos_result="mixed"``).
   Insert-only-if-missing (idempotent; a later F003 re-validation write is preserved).
2. ``trial_registry`` gets the 6 backtest configs (``B082_TRIALS``) — insert-only-missing
   on the deterministic content id (mirrors 0033/0036, so re-apply is a no-op).

A backend guard test asserts the seeded card round-trips byte-identical to the constant.

Revision ID: 0037_b082_dividend_lowvol_card
Revises: 0036_b081_card_capital_conditioned
Create Date: 2026-07-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workbench_api.monitoring.trial_backfill_b082 import (
    B082_TRIAL_STAMP,
    B082_TRIALS,
    CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT,
    CN_DIVIDEND_LOWVOL_STRATEGY_ID,
)

revision: str = "0037_b082_dividend_lowvol_card"
down_revision: str | Sequence[str] | None = "0036_b081_card_capital_conditioned"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CARD_TABLE = sa.table(
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

_TRIAL_TABLE = sa.table(
    "trial_registry",
    sa.column("id", sa.String),
    sa.column("created_at", sa.DateTime),
    sa.column("batch", sa.String),
    sa.column("strategy_id", sa.String),
    sa.column("parameter_hash", sa.String),
    sa.column("params", sa.JSON),
    sa.column("universe", sa.String),
    sa.column("window_start", sa.Date),
    sa.column("window_end", sa.Date),
    sa.column("oos_split", sa.String),
    sa.column("metrics", sa.JSON),
    sa.column("verdict", sa.String),
    sa.column("source_ref", sa.String),
    sa.column("notes", sa.String),
)


def upgrade() -> None:
    bind = op.get_bind()

    # 1) OOS card — insert only if the row is absent (idempotent; preserve later writes).
    existing_card = bind.execute(
        sa.text(
            "SELECT 1 FROM oos_verification_card WHERE strategy_id = :sid"
        ),
        {"sid": CN_DIVIDEND_LOWVOL_STRATEGY_ID},
    ).first()
    if existing_card is None:
        op.bulk_insert(
            _CARD_TABLE,
            [
                {
                    "strategy_id": CN_DIVIDEND_LOWVOL_STRATEGY_ID,
                    **CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT,
                    "source": "seed",
                    "updated_at": B082_TRIAL_STAMP,
                }
            ],
        )

    # 2) Backtest trials — insert-only-missing on the deterministic content id.
    existing = {row[0] for row in bind.execute(sa.text("SELECT id FROM trial_registry"))}
    rows = [
        {
            "id": t["id"],
            "created_at": B082_TRIAL_STAMP,
            "batch": t["batch"],
            "strategy_id": t["strategy_id"],
            "parameter_hash": None,
            "params": t["params"],
            "universe": t["universe"],
            "window_start": t["window_start"],
            "window_end": t["window_end"],
            "oos_split": t["oos_split"],
            "metrics": t["metrics"],
            "verdict": t["verdict"],
            "source_ref": t["source_ref"],
            "notes": None,
        }
        for t in B082_TRIALS
        if t["id"] not in existing
    ]
    if rows:
        op.bulk_insert(_TRIAL_TABLE, rows)


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM oos_verification_card WHERE strategy_id = :sid"),
        {"sid": CN_DIVIDEND_LOWVOL_STRATEGY_ID},
    )
    ids = [t["id"] for t in B082_TRIALS]
    bind.execute(
        sa.text("DELETE FROM trial_registry WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
