"""B081 F004 — the deploy-path registration test.

End-to-end alembic ``upgrade head`` must land BOTH B081 F004 seeds automatically (the
deploy chain runs ``alembic upgrade``, never bootstrap — the B080 F005 lesson): 0034
registers the 8 engine-fidelity A/B groups in ``trial_registry`` (DSR N), and 0035
updates the cn_attack OOS red card to the 更保守 engine-fidelity口径 (OOS -14.7%,
``validated`` still False). Also pins the B081_AB_TRIALS data contract (8 groups, real
metrics filled — not the PENDING placeholder — and old_all_off carries the B070
reproducibility note).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.monitoring.trial_backfill_b081 import B081_AB_TRIALS
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


def test_alembic_head_seeds_b081_trials_and_updates_card(tmp_db_url: str) -> None:
    _upgrade_head(tmp_db_url)
    with Session(get_engine()) as session:
        # 0034 — the 8 A/B groups are registered under batch B081.
        count = session.execute(
            text("SELECT COUNT(*) FROM trial_registry WHERE batch = 'B081'")
        ).scalar_one()
        assert count == 8

        # 0035 — the red card is updated to the engine-fidelity口径, still unvalidated.
        card = OosVerificationCardRepository(session).get_card("cn_attack_pure_momentum")
        assert card is not None
        assert card["validated"] is False
        assert card["oos_cagr_range"] == CN_ATTACK_RESEARCH_CAVEAT["oos_cagr_range"]
        assert "-14.7%" in card["oos_cagr_range"]
        assert "B081" in card["headline_zh"]
