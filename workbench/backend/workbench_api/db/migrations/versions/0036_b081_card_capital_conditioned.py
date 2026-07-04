"""B081 F005 r1 — capital-conditioned red-card correction + audit-trial landing.

The 0035 card update shipped a WRONG causal narrative ("the B070 +28.4% was largely
a fractional-share artifact; the strategy loses OOS"). The F005 independent audit
falsified it with a capital scan: the negative numbers are the 100k-CNY CAPACITY
FLOOR (≈9 of 25 equal-weight names cannot afford one 100-share lot; at 1M CNY the
pure-fidelity OOS is +27.1% ≈ 95% of the old edge, at 10M +28.2% ≈ 99%), and
``new_all_on`` additionally mixed in the un-verdicted ``partial_rebalance`` strategy
change. Planner adjudication c772c72: the card must be capital-conditioned and based
on the pure-fidelity baseline. ``validated`` stays False and ``oos_result`` stays
"negative" (the shipped paper accounts run at the 100k retail capital where the
lot-constrained OOS IS negative) — invariant ④ intact, wording corrected.

Also lands the 6 evaluator audit trials (capital scan + isolation groups — real
configs actually run, so they belong in the DSR ``N`` registry; insert-only-missing,
mirroring 0034).

Revision ID: 0036_b081_card_capital_conditioned
Revises: 0035_b081_oos_card_engine_fidelity
Create Date: 2026-07-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from workbench_api.monitoring.trial_backfill_b081 import (
    B081_AUDIT_TRIALS,
    B081_TRIAL_STAMP,
)
from workbench_api.strategy_modes.cn_attack_precompute import CN_ATTACK_RESEARCH_CAVEAT

revision: str = "0036_b081_card_capital_conditioned"
down_revision: str | Sequence[str] | None = "0035_b081_oos_card_engine_fidelity"
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
    # 1) Card correction — byte-identical to the (corrected) in-code fallback.
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
                "source": "b081_f005_capital_conditioned",
                "strategy_id": strategy_id,
            },
        )
    # 2) Audit trials — insert-only-missing (idempotent, mirrors 0034).
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
        for t in B081_AUDIT_TRIALS
        if t["id"] not in existing
    ]
    if rows:
        op.bulk_insert(_SEED_TABLE, rows)


def downgrade() -> None:
    # One-way wording correction; the prior (falsified) card text is recoverable
    # from 0035's history. Audit trials are removed by id.
    ids = [t["id"] for t in B081_AUDIT_TRIALS]
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM trial_registry WHERE id IN :ids").bindparams(
            sa.bindparam("ids", value=ids, expanding=True)
        )
    )
