"""B047-OPS2 F001 — backtest_data_window table + backtest_run.error_kind.

Adds:
- ``backtest_data_window`` — singleton row recording the real data coverage
  window (data_start / data_end / first_usable_signal_date) the data-refresh
  job writes; the request-path ``GET /api/backtests/data-range`` reads it.
- ``backtest_run.error_kind`` — structured error classification so the frontend
  maps a bilingual friendly message instead of leaking the raw exception.

Revision ID: 0014_b047_ops2_data_window_error_kind
Revises: 0013_b047_investment_report
Create Date: 2026-06-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_b047_ops2_data_window_error_kind"
down_revision: str | Sequence[str] | None = "0013_b047_investment_report"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_data_window",
        sa.Column("id", sa.String(length=16), primary_key=True, nullable=False),
        sa.Column("data_start", sa.Date(), nullable=False),
        sa.Column("data_end", sa.Date(), nullable=False),
        sa.Column("first_usable_signal_date", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "backtest_run",
        sa.Column("error_kind", sa.String(length=32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("backtest_run", "error_kind")
    op.drop_table("backtest_data_window")
