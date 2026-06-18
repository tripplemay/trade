"""B067 F001 — CN attack advisory precompute + mode registry tests.

Covers the F001 deliverables (spec §4 F001):

* the two CN attack advisory modes are registered (research-state, daily cadence)
  and dispatched to a producer — they auto-appear in the /api/strategy-modes
  selector source;
* the producer persists under its ``strategy_id`` (an injected fake target, no
  trade import) so the two variants are isolated and never trample each other;
* the persisted target ALWAYS sums to 1.0 via the explicit cash row (head trap);
* the ★OOS honesty caveat + 获利了结 (profit-take) ride along in master_meta and
  the per-row rationale (spec §0);
* a data-coverage failure classifies as ``data_not_covered`` (actionable), an
  unexpected one as ``scoring_error`` — never a silent all-cash publish.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.strategy_modes import get_target, list_modes
from workbench_api.strategy_modes.cn_attack_precompute import (
    CN_ATTACK_CASH_SYMBOL,
    CN_ATTACK_RESEARCH_CAVEAT,
    ERROR_KIND_DATA_NOT_COVERED,
    ERROR_KIND_SCORING,
    CnAttackPrecomputeError,
    CnAttackTargetResult,
    _build_target_result,
    run_cn_attack_precompute,
    score_cn_attack_target,
)
from workbench_api.strategy_modes.refresh_worker import _DISPATCH
from workbench_api.strategy_modes.registry import (
    CADENCE_DAILY,
    CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
    CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
    FUNDING_RESEARCH,
    REGIME_STRATEGY_ID,
)

_AS_OF = date(2025, 12, 31)


@pytest.fixture
def session(initialised_db: str) -> Iterator[Session]:  # noqa: ARG001
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    sess = factory()
    yield sess
    sess.close()


def _fake_target(
    *,
    strategy_id: str,
    factor_variant: str,
    rebalanced: bool = True,
    profit_take: list[str] | None = None,
) -> CnAttackTargetResult:
    """A ready-to-persist target (already summing to 1.0 with the cash row)."""

    return CnAttackTargetResult(
        as_of_date=_AS_OF,
        target_weights={"600519.SH": 0.4, "000858.SZ": 0.4, CN_ATTACK_CASH_SYMBOL: 0.2},
        symbol_sleeve={
            "600519.SH": "cn_attack",
            "000858.SZ": "cn_attack",
            CN_ATTACK_CASH_SYMBOL: "cash",
        },
        meta={
            "data_source": "fixture",
            "strategy_id": strategy_id,
            "factor_variant": factor_variant,
            "cadence": "daily",
            "signal_date": _AS_OF.isoformat(),
            "rebalanced": rebalanced,
            "profit_take": profit_take or [],
            "research_only": True,
            "research_caveat": dict(CN_ATTACK_RESEARCH_CAVEAT),
        },
    )


# --- mode registry ------------------------------------------------------------


def test_registry_lists_two_cn_attack_research_modes() -> None:
    by_id = {mode.id: mode for mode in list_modes()}
    assert {"cn_attack_quality_momentum", "cn_attack_pure_momentum"} <= set(by_id)
    for mode_id, sid in (
        ("cn_attack_quality_momentum", CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID),
        ("cn_attack_pure_momentum", CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID),
    ):
        mode = by_id[mode_id]
        assert mode.strategy_id == sid
        # Research-state honesty + daily cadence (B067).
        assert mode.funding_state == FUNDING_RESEARCH
        assert mode.is_research_state is True
        assert mode.cadence == CADENCE_DAILY
        # No per-mode backtest is wired off the registry (B066 backtest is separate).
        assert mode.backtest_key is None
    # Flagship still first; research modes (incl. cn_attack) come after.
    assert list_modes()[0].id == "master"


def test_cn_attack_modes_have_producers_wired() -> None:
    assert CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID in _DISPATCH
    assert CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID in _DISPATCH


def test_modes_surface_in_strategy_modes_service() -> None:
    from workbench_api.strategy_modes.service import list_strategy_modes

    by_strategy = {m.strategy_id: m for m in list_strategy_modes().modes}
    for sid in (
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
    ):
        assert sid in by_strategy
        assert by_strategy[sid].is_research_state is True
        assert by_strategy[sid].cadence == CADENCE_DAILY


# --- _build_target_result (pure: appends cash row + OOS meta) ------------------


def test_build_target_result_appends_cash_row_and_oos_caveat() -> None:
    from trade.backtest.cn_attack_momentum_quality.live import (  # type: ignore[import-untyped]
        CnAttackLiveTarget,
    )

    live = CnAttackLiveTarget(
        as_of_date=_AS_OF,
        signal_date=_AS_OF,
        factor_variant="quality_momentum",
        target_weights={"600519.SH": 0.5, "000858.SZ": 0.42},  # invested 0.92
        cash_weight=0.08,
        rebalanced=True,
        profit_take=("600036.SH",),
        would_be_turnover=0.55,
        no_trade_band=0.20,
        top_n=25,
    )
    result = _build_target_result(
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID, "quality_momentum", "real", live
    )
    # Explicit cash row appended → the persisted target sums to 1.0.
    assert result.target_weights[CN_ATTACK_CASH_SYMBOL] == pytest.approx(0.08)
    assert sum(result.target_weights.values()) == pytest.approx(1.0, abs=1e-9)
    assert result.symbol_sleeve[CN_ATTACK_CASH_SYMBOL] == "cash"
    # ★OOS honesty + profit-take ride along for the surface.
    assert result.meta["research_caveat"]["validated"] is False
    assert result.meta["research_caveat"]["oos_result"] == "negative"
    assert result.meta["profit_take"] == ["600036.SH"]
    assert result.meta["rebalanced"] is True
    assert result.meta["data_source"] == "real"


def test_build_target_result_omits_cash_row_when_fully_invested() -> None:
    from trade.backtest.cn_attack_momentum_quality.live import CnAttackLiveTarget

    live = CnAttackLiveTarget(
        as_of_date=_AS_OF,
        signal_date=_AS_OF,
        factor_variant="pure_momentum",
        target_weights={"600519.SH": 0.5, "000858.SZ": 0.5},  # invested 1.0
        cash_weight=0.0,
        rebalanced=False,
        profit_take=(),
        would_be_turnover=0.01,
        no_trade_band=0.20,
        top_n=25,
    )
    result = _build_target_result(
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID, "pure_momentum", "fixture", live
    )
    assert CN_ATTACK_CASH_SYMBOL not in result.target_weights
    assert sum(result.target_weights.values()) == pytest.approx(1.0, abs=1e-9)


# --- run_cn_attack_precompute: persistence via injected fake ------------------


def test_run_precompute_persists_under_strategy_and_sums_to_one(
    session: Session,
) -> None:
    fake = _fake_target(
        strategy_id=CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
        factor_variant="quality_momentum",
        profit_take=["600036.SH"],
    )
    summary = run_cn_attack_precompute(
        session,
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
        factor_variant="quality_momentum",
        score_fn=lambda: fake,
    )
    assert summary.error is None
    assert summary.saved == 3
    assert summary.as_of_date == _AS_OF

    target = get_target(session, CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID)
    assert target is not None
    assert abs(sum(target.weights.values()) - 1.0) < 1e-3
    rows = RecommendationSnapshotRepository(session).latest_snapshot(
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID
    )
    # ★OOS honesty caveat denormalised onto every row's master_meta.
    assert all(r.master_meta["research_caveat"]["validated"] is False for r in rows)
    # Rationale is research-state honest (no return prediction).
    assert all(r.rationale and "研究态" in r.rationale for r in rows)
    # 获利了结 rides in master_meta (sold names have no target row — they were sold).
    assert all(r.master_meta["profit_take"] == ["600036.SH"] for r in rows)


def test_two_variants_are_isolated(session: Session) -> None:
    run_cn_attack_precompute(
        session,
        CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
        factor_variant="quality_momentum",
        score_fn=lambda: _fake_target(
            strategy_id=CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
            factor_variant="quality_momentum",
        ),
    )
    run_cn_attack_precompute(
        session,
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        factor_variant="pure_momentum",
        score_fn=lambda: _fake_target(
            strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
            factor_variant="pure_momentum",
        ),
    )
    quality = get_target(session, CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID)
    pure = get_target(session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID)
    assert quality is not None and pure is not None
    # Each variant resolves its own target; neither trampled the other.
    assert quality.strategy_id == CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID
    assert pure.strategy_id == CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID
    assert quality.target_key != pure.target_key or quality.weights == pure.weights


def test_precompute_data_gap_is_actionable(session: Session) -> None:
    def no_data() -> CnAttackTargetResult:
        raise CnAttackPrecomputeError(
            "CN attack produced an empty (all-cash) target — run the A-share refresh."
        )

    summary = run_cn_attack_precompute(
        session,
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        factor_variant="pure_momentum",
        score_fn=no_data,
    )
    assert summary.saved == 0
    assert summary.error_kind == ERROR_KIND_DATA_NOT_COVERED
    assert get_target(session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID) is None


def test_precompute_unexpected_error_is_scoring_error(session: Session) -> None:
    def boom() -> CnAttackTargetResult:
        raise RuntimeError("scoring blew up")

    summary = run_cn_attack_precompute(
        session,
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        factor_variant="pure_momentum",
        score_fn=boom,
    )
    assert summary.saved == 0
    assert summary.error == "scoring blew up"
    assert summary.error_kind == ERROR_KIND_SCORING
    assert get_target(session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID) is None


def test_live_producer_keeps_equal_weighting_b069(monkeypatch: pytest.MonkeyPatch) -> None:
    # B069 decision (2026-06-19): the live cn_attack advisory default weighting STAYS
    # equal — B068's authoritative OOS did NOT support inverse_vol (lower OOS Sharpe +
    # CAGR; only a weak quality-mode drawdown benefit, survivorship-inflated). This
    # guard fails if the live producer is ever switched to inverse_vol without a fresh
    # decision (encodes the "keep equal" choice; see docs/dev/B069-...-decision.md).
    import trade.backtest.cn_attack_momentum_quality.live as live_mod  # type: ignore[import-untyped]
    from trade.backtest.cn_attack_momentum_quality.live import CnAttackLiveTarget
    from trade.strategies.cn_attack_momentum_quality.parameters import (  # type: ignore[import-untyped]
        WEIGHTING_SCHEME_EQUAL,
    )

    captured: dict[str, str] = {}

    def _capture(parameters: object) -> CnAttackLiveTarget:
        captured["weighting"] = parameters.weighting_scheme  # type: ignore[attr-defined]
        return CnAttackLiveTarget(
            as_of_date=_AS_OF,
            signal_date=_AS_OF,
            factor_variant=parameters.factor_variant,  # type: ignore[attr-defined]
            target_weights={"600519.SH": 1.0},
            cash_weight=0.0,
            rebalanced=True,
            profit_take=(),
            would_be_turnover=0.0,
            no_trade_band=0.20,
            top_n=25,
        )

    monkeypatch.setattr(live_mod, "compute_cn_attack_live_target", _capture)
    for sid, factor in (
        (CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID, "quality_momentum"),
        (CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID, "pure_momentum"),
    ):
        score_cn_attack_target(strategy_id=sid, factor_variant=factor)
        assert captured["weighting"] == WEIGHTING_SCHEME_EQUAL


def test_cn_attack_write_does_not_trample_regime(session: Session) -> None:
    # A cn_attack write on the same date must not delete another mode's rows
    # (the idempotent delete is scoped by strategy_id).
    RecommendationSnapshotRepository(session).save_batch(
        strategy_id=REGIME_STRATEGY_ID,
        as_of_date=_AS_OF,
        rows=[{"symbol": "SGOV", "sleeve": "defensive", "target_weight": 1.0}],
        master_meta={"data_source": "fixture"},
    )
    session.commit()
    run_cn_attack_precompute(
        session,
        CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
        factor_variant="pure_momentum",
        score_fn=lambda: _fake_target(
            strategy_id=CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
            factor_variant="pure_momentum",
        ),
    )
    regime = get_target(session, REGIME_STRATEGY_ID)
    assert regime is not None
    assert regime.weights == {"SGOV": 1.0}
