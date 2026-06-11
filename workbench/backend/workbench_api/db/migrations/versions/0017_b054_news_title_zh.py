"""B054 F-news — news.title_zh column (Simplified-Chinese headline).

Adds a nullable ``title_zh`` String(512) to the ``news`` table. Populated
off the request path by the ``news_translation`` batch job (LLM translate,
no-AI boundary rule (e)); NULL until translated. The global feed
(``GET /api/news/latest``) and the sleeve-news association both fall back
to the original English ``title`` when ``title_zh`` is NULL.

A localized headline is metadata, not raw article body, so this stays
within permanent product boundary **(p)** (news schema is metadata-only):
the column is a short String like ``title``, never a TEXT body column.

Revision ID: 0017_b054_news_title_zh
Revises: 0016_b043_risk_explanation_snapshot
Create Date: 2026-06-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017_b054_news_title_zh"
down_revision: str | Sequence[str] | None = "0016_b043_risk_explanation_snapshot"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "news",
        sa.Column("title_zh", sa.String(length=512), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("news", "title_zh")
