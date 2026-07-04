"""B081 F004 — update the cn_attack OOS red card to the engine-fidelity口径.

The card seeded by 0028 carried the B066 numbers (OOS -9%~-11%). The B081 A/B on the
B070 de-biased PIT, with realistic engine modeling (100-share lots etc.), found OOS CAGR
**-14.7%** — MORE conservative, and shows the apparent B070 +28.4% was largely a
fractional-share artifact. Per spec §2 F004 the card is updated in the 更保守 direction;
``validated`` stays hardcoded False. Existing DBs (production ran 0028) need this UPDATE;
a fresh DB gets the new values straight from 0028 (which seeds the current constant), so
this is a no-op there. Byte-identical to ``CN_ATTACK_RESEARCH_CAVEAT`` (imports it, like
0028) — the in-code fallback and the DB row stay in lockstep.

Revision ID: 0035_b081_oos_card_engine_fidelity
Revises: 0034_b081_engine_fidelity_ab_trials
Create Date: 2026-07-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workbench_api.strategy_modes.cn_attack_precompute import CN_ATTACK_RESEARCH_CAVEAT

revision: str = "0035_b081_oos_card_engine_fidelity"
down_revision: str | Sequence[str] | None = "0034_b081_engine_fidelity_ab_trials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_STRATEGY_IDS = ("cn_attack_quality_momentum", "cn_attack_pure_momentum")

_UPDATE = sa.text(
    "UPDATE oos_verification_card SET "
    "validated = :validated, oos_result = :oos_result, "
    "oos_cagr_range = :oos_cagr_range, headline_zh = :headline_zh, "
    "headline_en = :headline_en, detail_zh = :detail_zh, detail_en = :detail_en, "
    "backtest_ref = :backtest_ref, source = :source "
    "WHERE strategy_id = :strategy_id"
)


def upgrade() -> None:
    bind = op.get_bind()
    for strategy_id in _STRATEGY_IDS:
        bind.execute(
            _UPDATE,
            {
                "validated": CN_ATTACK_RESEARCH_CAVEAT["validated"],
                "oos_result": CN_ATTACK_RESEARCH_CAVEAT["oos_result"],
                "oos_cagr_range": CN_ATTACK_RESEARCH_CAVEAT["oos_cagr_range"],
                "headline_zh": CN_ATTACK_RESEARCH_CAVEAT["headline_zh"],
                "headline_en": CN_ATTACK_RESEARCH_CAVEAT["headline_en"],
                "detail_zh": CN_ATTACK_RESEARCH_CAVEAT["detail_zh"],
                "detail_en": CN_ATTACK_RESEARCH_CAVEAT["detail_en"],
                "backtest_ref": CN_ATTACK_RESEARCH_CAVEAT["backtest_ref"],
                "source": "b081_engine_fidelity",
                "strategy_id": strategy_id,
            },
        )


def downgrade() -> None:
    # One-way conservative update; the prior card is recoverable from 0028's history.
    pass
