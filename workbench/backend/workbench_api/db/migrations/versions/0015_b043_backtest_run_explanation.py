"""B043 F002 — backtest_run.explanation column.

Adds ``backtest_run.explanation`` — the grounded LLM "why this Sharpe/drawdown"
text the worker generates off the request path (nullable; the explanation is an
enhancement, so a refused / over-budget / LLM-down run still stores the full
backtest result with explanation NULL).

Revision ID: 0015_b043_backtest_run_explanation
Revises: 0014_b047_ops2_data_window_error_kind
Create Date: 2026-06-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015_b043_backtest_run_explanation"
down_revision: str | Sequence[str] | None = "0014_b047_ops2_data_window_error_kind"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "backtest_run",
        sa.Column("explanation", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("backtest_run", "explanation")
