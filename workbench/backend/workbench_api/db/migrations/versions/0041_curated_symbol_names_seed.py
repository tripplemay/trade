"""B087 F001 — auto-seed CURATED_SYMBOL_NAMES into symbol_name (deploy-chain fix).

B080 F005: bootstrap-only seeds never reach the alembic-run deploy chain, so production
had the curated display-names at **0** — raw tickers (e.g. ``AAPL`` instead of "Apple
Inc.") shown for the US names the A-share ``akshare_spot`` refresh doesn't cover. This
data-migration lands the curated seed on deploy (same deploy-safe pattern as the trial
migrations 0036–0040); the bootstrap CLI keeps local dev in lockstep via
``_import_symbol_names``.

★Insert-if-absent: a curated row is inserted only for a symbol not already present, so
this NEVER overwrites an ``akshare_spot`` name (curated is the fallback, akshare_spot the
override — priority preserved). Idempotent: re-running inserts nothing.

Revision ID: 0041_curated_symbol_names_seed
Revises: 0040_b085_residual_momentum_screen_trial
Create Date: 2026-07-05
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

from workbench_api.symbols.names import CURATED_SYMBOL_NAMES

revision: str = "0041_curated_symbol_names_seed"
down_revision: str | Sequence[str] | None = "0040_b085_residual_momentum_screen_trial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Deterministic stamp (Date.now() is unavailable in migrations / would break replays).
_STAMP = datetime(2026, 7, 5, tzinfo=UTC)

_SYMBOL_NAME = sa.table(
    "symbol_name",
    sa.column("symbol", sa.String),
    sa.column("name", sa.String),
    sa.column("source", sa.String),
    sa.column("updated_at", sa.DateTime),
)


def upgrade() -> None:
    bind = op.get_bind()
    existing = {row[0] for row in bind.execute(sa.text("SELECT symbol FROM symbol_name"))}
    rows = [
        {"symbol": symbol, "name": name, "source": "curated", "updated_at": _STAMP}
        for symbol, name in CURATED_SYMBOL_NAMES.items()
        if symbol not in existing  # never overwrite an akshare_spot / existing name
    ]
    if rows:
        op.bulk_insert(_SYMBOL_NAME, rows)


def downgrade() -> None:
    # Remove only the curated seed this migration lands (akshare_spot rows untouched).
    op.get_bind().execute(sa.text("DELETE FROM symbol_name WHERE source = 'curated'"))
