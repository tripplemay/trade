"""B081 F004 — the deploy-path registration test.

End-to-end alembic ``upgrade head`` must land the B081 seeds automatically (the
deploy chain runs ``alembic upgrade``, never bootstrap — the B080 F005 lesson): 0034
registers the 8 engine-fidelity A/B groups in ``trial_registry`` (DSR N), 0035+0036
update the cn_attack OOS red card — 0036 is the F005 r1 CORRECTION to the
capital-conditioned wording (10万 capacity floor −16.0% / 1M pure-fidelity +27.1%,
``validated`` still False) and lands the 6 evaluator audit trials. Also pins the
B081_AB_TRIALS data contract (8 groups, real metrics filled — not the PENDING
placeholder — and old_all_off carries the B070 reproducibility note).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.monitoring.trial_backfill_b081 import (
    B081_AB_TRIALS,
    B081_AUDIT_TRIALS,
)
from workbench_api.strategy_modes.cn_attack_precompute import CN_ATTACK_RESEARCH_CAVEAT


def _upgrade_head(tmp_db_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)
    command.upgrade(cfg, "head")


def test_b081_ab_trials_data_contract() -> None:
    # 8 groups, metrics filled (not the PENDING placeholder), deterministic ids.
    assert len(B081_AB_TRIALS) == 8
    labels = {t["params"]["description"].split(":")[0] for t in B081_AB_TRIALS}
    assert "old_all_off" in labels and "new_all_on" in labels
    for t in B081_AB_TRIALS:
        assert t["batch"] == "B081"
        assert t["metrics"]["summary"] != "PENDING A/B run"
        assert t["verdict"] == "NA"
    old = next(t for t in B081_AB_TRIALS if "old_all_off" in t["params"]["description"])
    assert "B070 signoff" in old["metrics"]["summary"]  # reproducibility recorded


def test_b081_audit_trials_data_contract() -> None:
    # F005 r1 — 6 audit groups (capital scan + isolation), metrics filled.
    assert len(B081_AUDIT_TRIALS) == 6
    labels = {t["params"]["description"].split(":")[0] for t in B081_AUDIT_TRIALS}
    assert "audit_lot_at_10m" in labels and "audit_fidelity_only_at_1m" in labels
    for t in B081_AUDIT_TRIALS:
        assert t["batch"] == "B081"
        assert "verifying-r1" in t["source_ref"]


def test_alembic_head_seeds_b081_trials_and_updates_card(tmp_db_url: str) -> None:
    _upgrade_head(tmp_db_url)
    with Session(get_engine()) as session:
        # 0034 (8 A/B groups) + 0036 (6 F005 audit groups) under batch B081.
        count = session.execute(
            text("SELECT COUNT(*) FROM trial_registry WHERE batch = 'B081'")
        ).scalar_one()
        assert count == 14

        # 0036 — the red card carries the F005 capital-conditioned correction:
        # the 10万 capacity floor is NOT read as strategy failure, the 1M
        # pure-fidelity number is disclosed, and ``validated`` stays False.
        card = OosVerificationCardRepository(session).get_card("cn_attack_pure_momentum")
        assert card is not None
        assert card["validated"] is False
        assert card["oos_cagr_range"] == CN_ATTACK_RESEARCH_CAVEAT["oos_cagr_range"]
        assert "-16.0%" in card["oos_cagr_range"]  # 10万 capacity floor
        assert "+27.1%" in card["oos_cagr_range"]  # 1M pure-fidelity retained edge
        assert "容量下限" in card["headline_zh"]
        assert "分数股假象" not in card["headline_zh"]  # falsified narrative removed
        assert "B081" in card["headline_zh"]
