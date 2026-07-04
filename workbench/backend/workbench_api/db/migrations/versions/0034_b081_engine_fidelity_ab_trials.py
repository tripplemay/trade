"""B081 F004 — auto-seed the 8 engine-fidelity A/B groups into trial_registry.

Same deploy-safe pattern as 0033 (the B080 trial backfill): the A/B groups are distinct
CONFIGS tried on the B070 PIT universe, so each is a trial for DSR ``N`` accounting. The
deploy chain runs ``alembic upgrade`` (never bootstrap), so the seed must land as a
data-migration. Idempotent: inserts only ids not already present (deterministic content
ids). ``old_all_off`` bit-level reproduces the B070 signoff (a reproducibility proof).

Revision ID: 0034_b081_engine_fidelity_ab_trials
Revises: 0033_b080_trial_backfill_seed
Create Date: 2026-07-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workbench_api.monitoring.trial_backfill_b081 import (
    B081_AB_TRIALS,
    B081_TRIAL_STAMP,
)

revision: str = "0034_b081_engine_fidelity_ab_trials"
down_revision: str | Sequence[str] | None = "0033_b080_trial_backfill_seed"
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
            "created_at": B081_TRIAL_STAMP,
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
        for t in B081_AB_TRIALS
        if t["id"] not in existing
    ]
    if rows:
        op.bulk_insert(_SEED_TABLE, rows)


def downgrade() -> None:
    ids = [t["id"] for t in B081_AB_TRIALS]
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM trial_registry WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
