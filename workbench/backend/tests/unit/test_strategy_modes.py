"""B057 F001 — strategy-mode platform layer.

Covers the four F001 deliverables:

* the mode registry (Master + regime modes, lookups, research-state honesty);
* the generic target layer (``get_target`` reads Master *and* regime from the
  same source; isolation between modes);
* the ``recommendation_snapshot`` repo scoped by ``strategy_id`` (a regime write
  never tramples Master's rows; Master read path unchanged — backward compat);
* the regime precompute (persists under ``regime_adaptive`` via an injected fake;
  and the *real* engine pipeline produces a non-degenerate target from synthetic
  records, summing to 1.0).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.paper.targets import (
    compute_target_key as paper_compute_target_key,
)
from workbench_api.paper.targets import (
    load_strategy_targets,
)
from workbench_api.strategy_modes import (
    MASTER_STRATEGY_ID,
    REGIME_STRATEGY_ID,
    compute_target_key,
    get_mode,
    get_target,
    list_modes,
    mode_for_strategy,
)
from workbench_api.strategy_modes.regime_precompute import (
    ERROR_KIND_DATA_NOT_COVERED,
    ERROR_KIND_SCORING,
    RegimePrecomputeError,
    RegimeTargetResult,
    _finalize_weights,
    compute_regime_target,
    run_regime_precompute,
)
from workbench_api.strategy_modes.registry import FUNDING_LIVE, FUNDING_RESEARCH, default_mode

_AS_OF = date(2025, 1, 31)
_META = {"data_source": "fixture"}


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _save(
    session: Session,
    *,
    strategy_id: str,
    as_of: date,
    weights: dict[str, float],
) -> None:
    rows = [
        {"symbol": sym, "sleeve": "test", "target_weight": w}
        for sym, w in weights.items()
    ]
    RecommendationSnapshotRepository(session).save_batch(
        strategy_id=strategy_id,
        as_of_date=as_of,
        rows=rows,
        master_meta=_META,
    )
    session.commit()


# --- mode registry ------------------------------------------------------------


def test_registry_has_master_and_regime_modes() -> None:
    modes = list_modes()
    ids = {mode.id for mode in modes}
    assert {"master", "regime"} <= ids
    # Master is the flagship default; the selector lists it first.
    assert modes[0].id == "master"
    assert default_mode().id == "master"


def test_registry_master_is_live_regime_is_research() -> None:
    master = get_mode("master")
    regime = get_mode("regime")
    assert master is not None and regime is not None
    assert master.strategy_id == MASTER_STRATEGY_ID
    assert regime.strategy_id == REGIME_STRATEGY_ID
    # Capability ≠ funding (B057 §1): Master is funded/live, regime research-state.
    assert master.funding_state == FUNDING_LIVE
    assert master.is_research_state is False
    assert regime.funding_state == FUNDING_RESEARCH
    assert regime.is_research_state is True
    # Cadence metadata: Master quarterly, regime monthly.
    assert master.cadence == "quarterly"
    assert regime.cadence == "monthly"


def test_registry_lookup_by_strategy_id() -> None:
    assert mode_for_strategy(MASTER_STRATEGY_ID) is get_mode("master")
    assert mode_for_strategy(REGIME_STRATEGY_ID) is get_mode("regime")
    assert mode_for_strategy("does-not-exist") is None
    assert get_mode("does-not-exist") is None


def test_list_strategy_modes_service_marks_research_state() -> None:
    # B057 F005 — the /api/strategy-modes data source for the frontend selector.
    from workbench_api.strategy_modes.service import list_strategy_modes

    resp = list_strategy_modes()
    by_strategy = {m.strategy_id: m for m in resp.modes}
    assert {MASTER_STRATEGY_ID, REGIME_STRATEGY_ID} <= set(by_strategy)
    assert by_strategy[MASTER_STRATEGY_ID].is_research_state is False
    assert by_strategy[MASTER_STRATEGY_ID].funding_state == "live"
    assert by_strategy[REGIME_STRATEGY_ID].is_research_state is True
    assert by_strategy[REGIME_STRATEGY_ID].funding_state == "research"
    assert by_strategy[REGIME_STRATEGY_ID].display_name == "智能择时组合"
    # Flagship first (selector order).
    assert resp.modes[0].strategy_id == MASTER_STRATEGY_ID


# --- generic target layer -----------------------------------------------------


def test_compute_target_key_is_deterministic_and_paper_reexport_matches() -> None:
    weights = {"SPY": 0.6, "SGOV": 0.4}
    key = compute_target_key(weights)
    # order-independent + rounding-stable
    assert key == compute_target_key({"SGOV": 0.40000001, "SPY": 0.6})
    # paper re-exports the canonical function (single source)
    assert paper_compute_target_key is compute_target_key
    assert key == paper_compute_target_key(weights)


def test_get_target_reads_master_and_regime_from_same_source(session: Session) -> None:
    _save(session, strategy_id=MASTER_STRATEGY_ID, as_of=_AS_OF, weights={"SPY": 0.7, "SGOV": 0.3})
    _save(session, strategy_id=REGIME_STRATEGY_ID, as_of=_AS_OF, weights={"QQQ": 0.5, "GLD": 0.5})

    master = get_target(session, MASTER_STRATEGY_ID)
    regime = get_target(session, REGIME_STRATEGY_ID)
    assert master is not None and regime is not None
    # Same function, different mode → isolated targets.
    assert master.weights == {"SPY": 0.7, "SGOV": 0.3}
    assert regime.weights == {"QQQ": 0.5, "GLD": 0.5}
    assert master.strategy_id == MASTER_STRATEGY_ID
    assert regime.strategy_id == REGIME_STRATEGY_ID
    assert master.as_of_date == _AS_OF
    assert master.target_key != regime.target_key


def test_get_target_defaults_to_master(session: Session) -> None:
    _save(session, strategy_id=MASTER_STRATEGY_ID, as_of=_AS_OF, weights={"SPY": 1.0})
    # Omitting the strategy resolves the Master target (B057 §2 backward compat).
    target = get_target(session)
    assert target is not None
    assert target.strategy_id == MASTER_STRATEGY_ID
    assert target.weights == {"SPY": 1.0}


def test_get_target_returns_none_for_absent_strategy(session: Session) -> None:
    assert get_target(session, REGIME_STRATEGY_ID) is None


# --- repo strategy_id scoping (Master backward compatibility) ------------------


def test_save_batch_regime_does_not_trample_master_same_date(session: Session) -> None:
    _save(session, strategy_id=MASTER_STRATEGY_ID, as_of=_AS_OF, weights={"SPY": 0.7, "SGOV": 0.3})
    # A regime write on the SAME as_of_date must NOT delete Master's rows
    # (the idempotent delete is scoped by strategy_id).
    _save(session, strategy_id=REGIME_STRATEGY_ID, as_of=_AS_OF, weights={"QQQ": 1.0})

    repo = RecommendationSnapshotRepository(session)
    master_rows = repo.latest_snapshot(MASTER_STRATEGY_ID)
    regime_rows = repo.latest_snapshot(REGIME_STRATEGY_ID)
    assert {r.symbol for r in master_rows} == {"SPY", "SGOV"}
    assert {r.symbol for r in regime_rows} == {"QQQ"}


def test_latest_snapshot_default_is_master_backward_compatible(session: Session) -> None:
    # The pre-B057 Master read path calls latest_snapshot() with no args.
    _save(session, strategy_id=MASTER_STRATEGY_ID, as_of=_AS_OF, weights={"SPY": 1.0})
    _save(session, strategy_id=REGIME_STRATEGY_ID, as_of=_AS_OF, weights={"QQQ": 1.0})
    rows = RecommendationSnapshotRepository(session).latest_snapshot()
    assert {r.symbol for r in rows} == {"SPY"}  # only Master, regime excluded


def test_latest_snapshot_is_per_strategy_max_date(session: Session) -> None:
    # Different cadences → different latest as_of_date per mode; each resolves
    # its OWN max date, never the global max.
    _save(session, strategy_id=MASTER_STRATEGY_ID, as_of=date(2025, 3, 31), weights={"SPY": 1.0})
    _save(session, strategy_id=REGIME_STRATEGY_ID, as_of=date(2025, 1, 31), weights={"QQQ": 1.0})
    regime = get_target(session, REGIME_STRATEGY_ID)
    assert regime is not None
    assert regime.as_of_date == date(2025, 1, 31)
    assert regime.weights == {"QQQ": 1.0}


def test_paper_load_strategy_targets_delegates_to_generic(session: Session) -> None:
    # B057: load_strategy_targets now resolves any mode with stored targets.
    _save(session, strategy_id=MASTER_STRATEGY_ID, as_of=_AS_OF, weights={"SPY": 0.6, "SGOV": 0.4})
    master = load_strategy_targets(session, MASTER_STRATEGY_ID)
    assert master is not None
    assert master.weights == {"SPY": 0.6, "SGOV": 0.4}
    assert master.target_key == compute_target_key(master.weights)
    assert load_strategy_targets(session, "unknown-strategy") is None


# --- _finalize_weights --------------------------------------------------------


def test_finalize_weights_drops_near_zero_and_normalises() -> None:
    out = _finalize_weights({"SPY": 0.5, "QQQ": 0.5, "VEA": 1e-9}, "SGOV")
    assert "VEA" not in out
    assert out == {"SPY": 0.5, "QQQ": 0.5}
    assert abs(sum(out.values()) - 1.0) < 1e-9


def test_finalize_weights_routes_residual_to_defensive() -> None:
    # A set that does not sum to 1.0 is renormalised; the residual lands on SGOV.
    out = _finalize_weights({"SPY": 0.3, "SGOV": 0.3}, "SGOV")
    assert abs(sum(out.values()) - 1.0) < 1e-6
    assert out["SGOV"] >= out["SPY"]  # defensive absorbed the residual


def test_finalize_weights_empty_when_all_zero() -> None:
    assert _finalize_weights({"SPY": 0.0, "SGOV": 0.0}, "SGOV") == {}


# --- regime precompute: persistence via injected fake -------------------------


def test_run_regime_precompute_persists_under_regime_strategy(session: Session) -> None:
    fake = RegimeTargetResult(
        as_of_date=_AS_OF,
        target_weights={"SPY": 0.5, "SGOV": 0.5},
        symbol_sleeve={"SPY": "risk_core", "SGOV": "defensive"},
        meta={"data_source": "fixture", "regime": "NORMAL"},
    )
    summary = run_regime_precompute(session, score_fn=lambda: fake)
    assert summary.error is None
    assert summary.saved == 2
    assert summary.as_of_date == _AS_OF
    assert summary.regime == "NORMAL"

    target = get_target(session, REGIME_STRATEGY_ID)
    assert target is not None
    assert target.weights == {"SPY": 0.5, "SGOV": 0.5}
    # Rationale is written + research-state honest (no return prediction).
    rows = RecommendationSnapshotRepository(session).latest_snapshot(REGIME_STRATEGY_ID)
    assert all(row.rationale and "研究态" in row.rationale for row in rows)
    # Master rows untouched (none were written).
    assert get_target(session, MASTER_STRATEGY_ID) is None


def test_run_regime_precompute_is_graceful_on_failure(session: Session) -> None:
    def boom() -> RegimeTargetResult:
        raise RuntimeError("scoring blew up")

    summary = run_regime_precompute(session, score_fn=boom)
    assert summary.saved == 0
    assert summary.error == "scoring blew up"
    # An UNEXPECTED error classifies as scoring_error (a real bug), not a data gap.
    assert summary.error_kind == ERROR_KIND_SCORING
    assert get_target(session, REGIME_STRATEGY_ID) is None


def test_run_regime_precompute_data_gap_is_actionable(session: Session) -> None:
    """B058 F003-PROD-1 — a data-coverage failure (RegimePrecomputeError, e.g. the
    unified prices file missing the regime ETFs) classifies as data_not_covered so
    the frontend can show "refresh the data" instead of a vague producer error."""

    def no_data() -> RegimeTargetResult:
        raise RegimePrecomputeError(
            "no price records available for the regime universe; missing "
            "['DBC', 'IEF', 'QQQ', 'TLT', 'VWO']"
        )

    summary = run_regime_precompute(session, score_fn=no_data)
    assert summary.saved == 0
    assert summary.error_kind == ERROR_KIND_DATA_NOT_COVERED
    assert "DBC" in (summary.error or "")
    assert get_target(session, REGIME_STRATEGY_ID) is None


# --- regime precompute: the REAL engine pipeline on synthetic records ----------


def _short_regime_config() -> object:
    from trade.strategies.regime_adaptive.config import (  # type: ignore[import-untyped]
        default_regime_adaptive_config,
    )

    # risk_parity requires vol_lookback ∈ {60, 120, 252}; keep trend_window ≥
    # vol_lookback so an asset that passes trend gating always has enough vol
    # history (mirrors the production config's 200 ≥ 120 relationship). Shorter
    # than production purely to keep the synthetic-records test fast.
    return replace(
        default_regime_adaptive_config(),
        trend_window_days=70,  # > vol_lookback so a trend-passing date has 60+ returns
        vol_lookback_days=60,
        regime_fast_vol_window_days=10,
        regime_slow_vol_window_days=30,
    )


def _build_regime_records(length: int = 160) -> tuple[object, ...]:
    """9-asset regime universe over ``length`` consecutive days, risk assets
    rising with deterministic oscillation (so the trend gating passes — bullish
    NORMAL regime — *and* risk_parity has non-zero volatility to weight on).
    Mirrors the regime backtest test fixtures."""

    import math

    from trade.data.loader import PriceBar  # type: ignore[import-untyped]
    from trade.strategies.regime_adaptive.config import (
        ASSET_CATEGORY_DEFENSIVE,
        default_regime_adaptive_config,
    )

    start = date(2024, 1, 1)
    config = default_regime_adaptive_config()
    rows: list[object] = []
    for index, entry in enumerate(config.universe):
        if entry.category == ASSET_CATEGORY_DEFENSIVE:
            series = [100.0 for _ in range(length)]  # flat defensive (residual sink)
        else:
            step = 0.25 + 0.03 * index  # uptrend dominates → passes trend gating
            amplitude = 1.0 + 0.4 * index  # per-asset vol so inverse-vol differentiates
            series = [
                100.0 + step * day + amplitude * math.sin(0.4 * day + index)
                for day in range(length)
            ]
        rows.extend(
            PriceBar(
                date=start + timedelta(days=day),
                symbol=entry.symbol,
                open=price * 0.999,
                close=price,
                adjusted_close=price,
                volume=1_000,
            )
            for day, price in enumerate(series)
        )
    return tuple(rows)


def test_compute_regime_target_produces_real_nondegenerate_target() -> None:
    records = _build_regime_records(length=160)
    result = compute_regime_target(
        records, prices_source="fixture", config=_short_regime_config()
    )
    # A real, fully-allocated target from the unchanged regime engine.
    assert result.target_weights
    assert abs(sum(result.target_weights.values()) - 1.0) < 1e-3
    assert all(w > 0 for w in result.target_weights.values())
    # In a rising market the regime resolves NORMAL and holds risk assets, not
    # 100% defensive — a meaningful (non-degenerate) allocation.
    assert result.meta["regime"] in {"NORMAL", "BEAR", "CRISIS"}
    assert result.meta["regime"] == "NORMAL"
    assert set(result.target_weights) - {"SGOV"}, "should hold more than the defensive asset"
    # as_of is a real monthly signal date strictly before the last observed date.
    assert result.as_of_date < records[-1].date  # type: ignore[attr-defined]
    assert result.meta["cadence"] == "monthly"


def test_compute_regime_target_persists_through_run(session: Session) -> None:
    records = _build_regime_records(length=160)
    config = _short_regime_config()
    summary = run_regime_precompute(
        session,
        score_fn=lambda: compute_regime_target(
            records, prices_source="fixture", config=config
        ),
    )
    assert summary.error is None
    assert summary.saved >= 1
    target = get_target(session, REGIME_STRATEGY_ID)
    assert target is not None
    assert abs(sum(target.weights.values()) - 1.0) < 1e-3
