"""B071 F003 — deterministic recommendation scoring on the golden fixture.

The recommendation precompute scorer (``score_master_target``) reads prices
through the same ``trade.data.loader.load_prices`` seam the backtests use. F003
threads a ``fixture_dir`` through it so CI can score the Master target on the
committed golden real-data fixture deterministically (same input → same
weights, no VM data root, no live wire).

Pure-scoring assertions (no DB); the DB-writing ``run_precompute`` path stays in
its existing tests. The weight-sum invariant is also pinned here as the
recommendation-side anchor of F004 invariant ②.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from workbench_api.recommendations.precompute import score_master_target

# workbench/backend/tests/unit/<this> → parents[4] is the repo root.
GOLDEN_DIR = Path(__file__).resolve().parents[4] / "data" / "fixtures" / "golden"


def test_golden_fixture_present() -> None:
    assert (GOLDEN_DIR / "prices_daily.csv").is_file(), (
        "golden fixture missing — B071 F002 must land before F003 scoring tests"
    )


def test_score_master_target_on_golden_is_deterministic() -> None:
    """Same golden fixture → bit-identical target weights on rerun."""
    first = score_master_target(fixture_dir=GOLDEN_DIR)
    second = score_master_target(fixture_dir=GOLDEN_DIR)
    assert first.target_weights == second.target_weights
    assert first.master_meta["data_source"] == second.master_meta["data_source"]


def test_score_master_target_on_golden_weights_sum_to_one() -> None:
    """F004 invariant ② (recommendation side): the target is a valid portfolio."""
    result = score_master_target(fixture_dir=GOLDEN_DIR)
    assert sum(result.target_weights.values()) == pytest.approx(1.0, abs=1e-4)
    assert all(weight >= 0 for weight in result.target_weights.values())


def test_score_master_target_on_golden_scores_real_data() -> None:
    """Golden has daily real prices for every sleeve, so each sleeve scores
    (none stubbed to the defensive fallback for want of data); the top-level
    provenance is the honest committed-fixture label."""
    result = score_master_target(fixture_dir=GOLDEN_DIR)
    assert set(result.master_meta["sleeve_status"]) == {
        "momentum",
        "risk_parity",
        "satellite_us_quality",
        "satellite_hk_china",
    }
    # golden → DATA_SOURCE_FIXTURE (committed test data, not live VM data).
    assert result.master_meta["data_source"] == "fixture"
