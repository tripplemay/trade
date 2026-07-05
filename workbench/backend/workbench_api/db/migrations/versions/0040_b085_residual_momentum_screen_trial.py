"""B085 F001 — auto-seed the residual-momentum IC screen trial into trial_registry.

Same deploy-safe pattern as 0038/0039 (alembic upgrade, never bootstrap — B080 F005): a
first-look screen is a distinct CONFIG tried → DSR ``N``. Idempotent by content id.

Revision ID: 0040_b085_residual_momentum_screen_trial
Revises: 0039_b084_etf_trend_trial
Create Date: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workbench_api.monitoring.trial_backfill_b085 import (
    B085_TRIAL_STAMP,
    B085_TRIALS,
)

revision: str = "0040_b085_residual_momentum_screen_trial"
down_revision: str | Sequence[str] | None = "0039_b084_etf_trend_trial"
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
            "created_at": B085_TRIAL_STAMP,
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
        for t in B085_TRIALS
        if t["id"] not in existing
    ]
    if rows:
        op.bulk_insert(_SEED_TABLE, rows)


def downgrade() -> None:
    ids = [t["id"] for t in B085_TRIALS]
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM trial_registry WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
