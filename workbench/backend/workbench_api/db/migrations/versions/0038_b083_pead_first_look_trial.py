"""B083 F002 — auto-seed the PEAD first-look IC trial into trial_registry.

Same deploy-safe pattern as 0034 (alembic upgrade, never bootstrap — B080 F005): the
PEAD 业绩预告 first-look is a distinct CONFIG tried (verdict INCONCLUSIVE), so it counts
toward DSR ``N``. Idempotent: inserts only if the deterministic content id is absent.

Revision ID: 0038_b083_pead_first_look_trial
Revises: 0037_b082_dividend_lowvol_card
Create Date: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workbench_api.monitoring.trial_backfill_b083 import (
    B083_TRIAL_STAMP,
    B083_TRIALS,
)

revision: str = "0038_b083_pead_first_look_trial"
down_revision: str | Sequence[str] | None = "0037_b082_dividend_lowvol_card"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_SEED_TABLE = sa.table(
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
    existing = {row[0] for row in bind.execute(sa.text("SELECT id FROM trial_registry"))}
    rows = [
        {
            "id": t["id"],
            "created_at": B083_TRIAL_STAMP,
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
        for t in B083_TRIALS
        if t["id"] not in existing
    ]
    if rows:
        op.bulk_insert(_SEED_TABLE, rows)


def downgrade() -> None:
    ids = [t["id"] for t in B083_TRIALS]
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM trial_registry WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
