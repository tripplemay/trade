"""B080 F003 — the three re-validation landings + the no-validated→True invariant."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.db.repositories.trial_registry import TrialRegistryRepository
from workbench_api.monitoring.reverify_landings import land_results

_SID = "cn_attack_pure_momentum"
_AS_OF = date(2026, 7, 3)


def _payload(verdict: str, oos_cagr: float, oos_sharpe: float) -> dict[str, Any]:
    return {
        "window": "2019-04-01..2026-07-03",
        "factor_variant": "pure_momentum",
        "weighting_scheme": "equal",
        "pit": {
            "full_cagr": 0.131, "full_sharpe": 0.56,
            "oos_cagr": oos_cagr, "oos_sharpe": oos_sharpe,
        },
        "control": {
            "full_cagr": 0.288, "full_sharpe": 0.93,
            "oos_cagr": 0.55, "oos_sharpe": 1.45,
        },
        "judgment": {
            "verdict": verdict, "reason": "test",
            "survivorship_bias_full_cagr": 0.157,
            "survivorship_bias_oos_cagr": 0.266,
            "survivorship_bias_oos_sharpe": 0.52,
        },
        "cpcv_lite": {
            "label": "CPCV-lite: not full CPCV", "n_splits": 2,
            "oos_cagr_mean": 0.2, "oos_sharpe_mean": 0.8, "oos_positive_frac": 1.0,
            "splits": [
                {"index": 1, "oos_start": "2024-01-01", "oos_end": "2025-01-01",
                 "oos_cagr": 0.25, "oos_sharpe": 0.9},
            ],
        },
    }


def test_positive_revalidation_never_validates_card(initialised_db: str, tmp_path: Path) -> None:
    # A GREAT (positive, SURVIVES) re-validation must STILL leave validated=False —
    # this pipeline can never un-watch a red card (§3 invariant ②).
    with Session(get_engine()) as session:
        out = land_results(
            session, strategy_id=_SID,
            payload=_payload("SURVIVES_DEBIASING", 0.284, 0.93),
            as_of=_AS_OF, repo_root=tmp_path,
        )
        session.commit()
        assert out["validated"] is False
        assert out["verdict"] == "GO"  # double-gate: holds → maintain
        card = OosVerificationCardRepository(session).get_card(_SID)
        assert card is not None and card["validated"] is False
        # The honest fresh number is recorded, but never validated.
        assert "28.4%" in card["oos_cagr_range"]
        # Trial registered with the double-gate verdict.
        trials = TrialRegistryRepository(session).list_by_strategy(_SID)
        assert len(trials) == 1 and trials[0].verdict == "GO"
        assert trials[0].batch == "reverify"
        # md report written under docs/test-reports/auto/.
        report = (
            tmp_path / "docs" / "test-reports" / "auto"
            / f"reverify-{_SID}-{_AS_OF.isoformat()}.md"
        )
        assert report.is_file()
        assert "parameters frozen" in report.read_text(encoding="utf-8")


def test_collapse_revalidation_flags_no_go(initialised_db: str, tmp_path: Path) -> None:
    with Session(get_engine()) as session:
        out = land_results(
            session, strategy_id=_SID,
            payload=_payload("COLLAPSES_DEBIASING", -0.09, -1.0),
            as_of=_AS_OF, repo_root=tmp_path,
        )
        session.commit()
        assert out["validated"] is False
        assert out["verdict"] == "NO_GO"
        card = OosVerificationCardRepository(session).get_card(_SID)
        assert card is not None and card["validated"] is False
        assert card["oos_result"] == "negative"
