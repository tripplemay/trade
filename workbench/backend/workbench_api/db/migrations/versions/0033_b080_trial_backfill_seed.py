"""B080 F005 fix — auto-seed the 27 historical trials into trial_registry.

F001's other seed (the OOS red card) auto-deployed via migration 0028's
``op.bulk_insert``, but the trial backfill lived ONLY in the manual
``workbench-bootstrap`` CLI (migration 0029 created the table but not the rows).
The deploy chain runs ``alembic upgrade`` and never bootstrap, so production shipped
with ``trial_registry`` empty (F005 L2 finding: DSR ``N`` started at 0). This
data-migration lands the backfill the SAME way the red card does — automatically on
deploy — using the identical source data + stamp as the CLI, so the two paths are
byte-identical. Idempotent: it inserts only ids not already present (the CLI upsert
and this migration converge on the same deterministic content ids).

Revision ID: 0033_b080_trial_backfill_seed
Revises: 0032_b080_cn_attack_paper_cny
Create Date: 2026-07-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workbench_api.monitoring.trial_backfill import (
    HISTORICAL_TRIALS,
    TRIAL_BACKFILL_STAMP,
)

revision: str = "0033_b080_trial_backfill_seed"
down_revision: str | Sequence[str] | None = "0032_b080_cn_attack_paper_cny"
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
            "created_at": TRIAL_BACKFILL_STAMP,
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
        for t in HISTORICAL_TRIALS
        if t["id"] not in existing
    ]
    if rows:
        op.bulk_insert(_SEED_TABLE, rows)


def downgrade() -> None:
    ids = [t["id"] for t in HISTORICAL_TRIALS]
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM trial_registry WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
