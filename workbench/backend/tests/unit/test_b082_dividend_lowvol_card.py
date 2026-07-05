"""B082 F002 — deploy-path registration + card byte-identity guard.

The auto-deploy chain runs ``alembic upgrade`` (never bootstrap — B080 F005 lesson), so
migration 0037 must land BOTH seeds on its own: the new ``cn_dividend_lowvol`` OOS card
(``validated=False``, ``oos_result="mixed"``) seeded byte-identical to
``CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT``, and the 6 backtest configs in ``trial_registry``.
Also pins the constant's data contract (three-tier 焊死 thresholds disclosed; the honest
"drawdown protection but no return uplift" defensive-sleeve framing).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.monitoring.trial_backfill_b082 import (
    B082_TRIALS,
    CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT,
    CN_DIVIDEND_LOWVOL_STRATEGY_ID,
)


def _upgrade_head(tmp_db_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    backend_root = __file__.rsplit("/tests/", 1)[0]
    cfg = Config(f"{backend_root}/alembic.ini")
    cfg.set_main_option("script_location", f"{backend_root}/workbench_api/db/migrations")
    cfg.set_main_option("sqlalchemy.url", tmp_db_url)
    command.upgrade(cfg, "head")


def test_b082_trials_data_contract() -> None:
    # 6 configs: primary strategy + baseline, implementable strategy + baseline @2 capitals.
    assert len(B082_TRIALS) == 6
    ids = [t["id"] for t in B082_TRIALS]
    assert len(set(ids)) == 6  # deterministic, unique
    for t in B082_TRIALS:
        assert t["batch"] == "B082"
        assert t["strategy_id"] == CN_DIVIDEND_LOWVOL_STRATEGY_ID
        assert t["verdict"] in {"INCONCLUSIVE", "NA"}
        assert t["metrics"]["summary"]  # non-empty, real numbers
        assert t["source_ref"] == "docs/test-reports/B082-F002-backtest.md"
    # The dual-capital implementable rows are both present (B081 容量 lesson coverage).
    descriptions = " ".join(t["params"]["description"] for t in B082_TRIALS)
    assert "@10万" in descriptions and "@100万" in descriptions


def test_b082_card_constant_contract() -> None:
    card = CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT
    # Invariant ② — validated=False start; honest two-sided result.
    assert card["validated"] is False
    assert card["oos_result"] == "mixed"
    assert set(card) == {
        "validated", "oos_result", "oos_cagr_range", "headline_zh",
        "headline_en", "detail_zh", "detail_en", "backtest_ref",
    }
    # The 焊死 three-tier thresholds are disclosed, and the defensive framing is explicit.
    assert "2.5%" in card["headline_zh"] and "1.5" in card["headline_zh"]
    assert "禁回测扫参" in card["headline_zh"] or "禁扫参" in card["headline_zh"]
    assert "不增收益" in card["headline_zh"]  # no return uplift — the honest finding
    assert "never backtest-tuned" in card["headline_en"]


def test_upsert_roundtrips_card_byte_identical(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = OosVerificationCardRepository(session)
        # Exactly what the seed migration writes (from the same constant).
        repo.upsert_card(CN_DIVIDEND_LOWVOL_STRATEGY_ID, CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT)
        session.commit()
        got = repo.get_card(CN_DIVIDEND_LOWVOL_STRATEGY_ID)
        assert got == CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT  # every U+2212/CJK char intact


def test_alembic_head_seeds_b082_card_and_trials(tmp_db_url: str) -> None:
    _upgrade_head(tmp_db_url)
    with Session(get_engine()) as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM trial_registry WHERE batch = 'B082'")
        ).scalar_one()
        assert count == 6

        card = OosVerificationCardRepository(session).get_card(
            CN_DIVIDEND_LOWVOL_STRATEGY_ID
        )
        assert card is not None
        assert card == CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT  # byte-identical seed
        assert card["validated"] is False
        assert card["oos_result"] == "mixed"
