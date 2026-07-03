"""B080 F001 — trial_registry: backfill count/idempotency + DSR N + verbatim.

Guards the historical backfill (≥15 trials, spec §2 F001), the deterministic-id
idempotency (re-seed must not inflate the DSR ``N``), the per-strategy count that
IS the DSR ``N``, and that 3 spot-checked rows carry the signoff numbers verbatim.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.trial_registry import TrialRegistryRepository
from workbench_api.monitoring.trial_backfill import HISTORICAL_TRIALS

_STAMP = datetime(2026, 7, 3, tzinfo=UTC)


def _seed(session: Session) -> TrialRegistryRepository:
    repo = TrialRegistryRepository(session)
    for trial in HISTORICAL_TRIALS:
        repo.register(created_at=_STAMP, **trial)
    session.commit()
    return repo


def test_backfill_has_at_least_15_trials() -> None:
    assert len(HISTORICAL_TRIALS) >= 15
    # Every deterministic id is unique (no accidental collisions inflating/merging N).
    assert len({t["id"] for t in HISTORICAL_TRIALS}) == len(HISTORICAL_TRIALS)


def test_backfill_seed_is_idempotent(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = _seed(session)
        assert repo.count() == len(HISTORICAL_TRIALS)
        # Re-seed (deterministic id → upsert in place) must not stack rows.
        _seed(session)
        assert repo.count() == len(HISTORICAL_TRIALS)


def test_count_by_strategy_is_dsr_n(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = _seed(session)
        # cn_attack_quality_momentum: B066 x3, B068 x2, B075 x1, B076-secondary x4 = 10.
        assert repo.count_by_strategy("cn_attack_quality_momentum") == 10
        # cn_attack_pure_momentum: B066 x3, B068 x2, B070 x2, B075 x1, B076-primary x4 = 12.
        assert repo.count_by_strategy("cn_attack_pure_momentum") == 12
        totals = repo.counts_by_strategy()
        assert sum(totals.values()) == len(HISTORICAL_TRIALS)


def test_spot_check_three_rows_verbatim(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = _seed(session)
        by_summary = {
            row.metrics["summary"]: row for row in repo.list_recent(limit=100)
        }
        # 1) B070 first de-biased GO (survivorship-free PIT).
        b070 = next(r for r in by_summary.values() if r.batch == "B070" and r.verdict == "GO")
        assert "OOS_CAGR 28.4% / OOS_Sharpe 0.93" in b070.metrics["summary"]
        assert b070.source_ref == (
            "docs/test-reports/B070-ashare-survivorship-free-signoff-2026-06-19.md"
        )
        # 2) B063 real held SGOV all quarters (hypothesis untested) — NO_GO.
        b063 = next(
            r
            for r in by_summary.values()
            if r.batch == "B063"
            and r.strategy_id == "hk_china_real"
            and "matched" not in r.params["description"]
        )
        assert "CAGR -0.06% / Sharpe -0.322" in b063.metrics["summary"]
        assert b063.verdict == "NO_GO"
        # 3) B077 smart-money LHB net-buy amount, weak IC.
        b077 = next(
            r for r in by_summary.values()
            if r.batch == "B077" and "机构买入净额" in r.params["description"]
        )
        assert "rank-IC N1 0.0201 / N5 0.0232" in b077.metrics["summary"]
        assert b077.verdict == "INCONCLUSIVE"


def test_register_rejects_unknown_verdict(initialised_db: str) -> None:
    with (
        Session(get_engine()) as session,
        pytest.raises(ValueError, match="invalid trial verdict"),
    ):
        TrialRegistryRepository(session).register(
            id="x", batch="B999", strategy_id="s", verdict="MAYBE"
        )
