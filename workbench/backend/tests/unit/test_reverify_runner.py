"""B080 F003 — reverify runner orchestration (append → kernel → landings)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.monitoring.reverify_runner import run_reverify

_SID = "cn_attack_pure_momentum"
_AS_OF = date(2026, 7, 3)


def _fake_payload() -> dict[str, Any]:
    return {
        "window": "2019-04-01..2026-07-03",
        "factor_variant": "pure_momentum",
        "weighting_scheme": "equal",
        "pit": {"full_cagr": 0.13, "full_sharpe": 0.5, "oos_cagr": 0.2, "oos_sharpe": 0.8},
        "control": {"full_cagr": 0.28, "full_sharpe": 0.9, "oos_cagr": 0.5, "oos_sharpe": 1.4},
        "judgment": {
            "verdict": "SURVIVES_DEBIASING", "reason": "test",
            "survivorship_bias_full_cagr": 0.15,
            "survivorship_bias_oos_cagr": 0.3, "survivorship_bias_oos_sharpe": 0.6,
        },
        "cpcv_lite": {
            "label": "CPCV-lite: not full CPCV", "n_splits": 1,
            "oos_cagr_mean": 0.2, "oos_sharpe_mean": 0.8, "oos_positive_frac": 1.0,
            "splits": [{"index": 1, "oos_start": "2024-01-01", "oos_end": "2025-01-01",
                        "oos_cagr": 0.2, "oos_sharpe": 0.8}],
        },
    }


def test_runner_wires_all_three_steps(initialised_db: str, tmp_path: Path) -> None:
    calls: dict[str, Any] = {}

    def fake_append(**kwargs: Any) -> dict[str, object]:
        calls["append"] = kwargs
        return {"priced": 800}

    def fake_kernel(root: Path, *, end: date) -> dict[str, Any]:
        calls["kernel"] = (root, end)
        return _fake_payload()

    with Session(get_engine()) as session:
        out = run_reverify(
            session, strategy_id=_SID, as_of=_AS_OF, repo_root=tmp_path,
            b070_root=tmp_path / "b070", reverify_root=tmp_path / "rvf",
            append_fn=fake_append, kernel_fn=fake_kernel,
        )
        session.commit()
        # All three steps ran, in order, with the reverify root threaded through.
        assert calls["append"]["reverify_root"] == tmp_path / "rvf"
        assert calls["kernel"] == (tmp_path / "rvf", _AS_OF)
        assert out["verdict"] == "GO"
        assert out["validated"] is False  # the invariant still holds through the runner
        card = OosVerificationCardRepository(session).get_card(_SID)
        assert card is not None and card["validated"] is False


def test_runner_can_skip_append(initialised_db: str, tmp_path: Path) -> None:
    appended = {"n": 0}

    def fake_append(**kwargs: Any) -> dict[str, object]:
        appended["n"] += 1
        return {}

    with Session(get_engine()) as session:
        run_reverify(
            session, strategy_id=_SID, as_of=_AS_OF, repo_root=tmp_path,
            b070_root=tmp_path, reverify_root=tmp_path, do_append=False,
            append_fn=fake_append, kernel_fn=lambda root, *, end: _fake_payload(),
        )
        session.commit()
        assert appended["n"] == 0  # data-append skipped
