"""B111 F003 (P0-3) regression: the frozen-target + zero-monitoring blind spot.

Three defences the P0-3 diagnosis calls for:
  * a target-staleness alert (the regime target froze for 7 weeks with no alert);
  * master + regime added to the monitoring cohort (they were excluded — the
    direct reason all three P0s ran unmonitored);
  * daily crisis re-evaluation (a crisis strategy that hadn't looked at the
    market in 7 weeks), decoupled from the monthly rebalance.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.monitoring_metric import MonitoringMetricRepository
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.monitoring.metrics_job import run_monitoring
from workbench_api.monitoring.staleness import (
    TARGET_STALENESS_ALERT_DAYS,
    assess_target_staleness,
)
from workbench_api.strategy_modes.regime_precompute import evaluate_current_regime

_AS_OF = date(2026, 7, 21)


# ── staleness verdict (pure) ─────────────────────────────────────────────────


def test_staleness_fresh_within_threshold() -> None:
    v = assess_target_staleness("regime_adaptive", date(2026, 7, 1), _AS_OF)
    assert v.is_stale is False
    assert v.age_days == 20


def test_staleness_stale_past_threshold_catches_p0_freeze() -> None:
    # The exact P0-3 freeze: target stuck at 2026-05-29, evaluated 2026-07-21.
    v = assess_target_staleness("regime_adaptive", date(2026, 5, 29), _AS_OF)
    assert v.age_days == 53
    assert v.age_days > TARGET_STALENESS_ALERT_DAYS
    assert v.is_stale is True


def test_staleness_boundary_is_exclusive() -> None:
    exactly = _AS_OF - timedelta(days=TARGET_STALENESS_ALERT_DAYS)
    assert assess_target_staleness("m", exactly, _AS_OF).is_stale is False
    assert assess_target_staleness("m", exactly - timedelta(days=1), _AS_OF).is_stale is True


def test_staleness_missing_target_is_stale() -> None:
    v = assess_target_staleness("regime_adaptive", None, _AS_OF)
    assert v.is_stale is True
    assert v.age_days is None


# ── daily crisis evaluation (evaluate ≠ trade) ──────────────────────────────


def _spy_records(series: list[float], symbol: str) -> tuple[Any, ...]:
    from trade.data.loader import PriceBar  # type: ignore[import-untyped]

    start = date(2024, 1, 1)
    return tuple(
        PriceBar(
            date=start + timedelta(days=i),
            symbol=symbol,
            open=px * 0.999,
            close=px,
            adjusted_close=px,
            volume=1_000,
        )
        for i, px in enumerate(series)
    )


def test_evaluate_current_regime_flags_crisis_on_latest_data() -> None:
    from trade.strategies.regime_adaptive.config import (  # type: ignore[import-untyped]
        default_regime_adaptive_config,
    )

    config = default_regime_adaptive_config()
    spy = config.regime_spy_symbol
    series = [100.0]
    for i in range(1, config.trend_window_days + 20):
        series.append(series[-1] * (1.0 + (0.001 if i % 2 else -0.001)))
    for i in range(20):  # sharp, volatile drop → below SMA + fast/slow ratio up
        series.append(series[-1] * (0.95 if i % 2 == 0 else 1.01))
    records = _spy_records(series, spy)

    state = evaluate_current_regime(records, {spy: 1.0}, config)
    assert state.regime == "CRISIS"
    assert state.spy_trend_signal is False
    # Uses the LATEST observed date (the current, possibly-partial month).
    assert state.triggered_at == records[-1].date


def test_evaluate_current_regime_normal_on_uptrend() -> None:
    from trade.strategies.regime_adaptive.config import (
        default_regime_adaptive_config,
    )

    config = default_regime_adaptive_config()
    spy = config.regime_spy_symbol
    series = [100.0 + 0.5 * i for i in range(config.trend_window_days + 40)]
    records = _spy_records(series, spy)

    state = evaluate_current_regime(records, {spy: 1.0}, config)
    assert state.regime == "NORMAL"
    assert state.spy_trend_signal is True


# ── monitoring covers master/regime: staleness metric + alert ───────────────


def _seed_target(
    session: Session, strategy_id: str, as_of: date, rows: list[dict[str, Any]]
) -> None:
    RecommendationSnapshotRepository(session).save_batch(
        strategy_id=strategy_id, as_of_date=as_of, rows=rows, master_meta={}
    )


def test_run_monitoring_alerts_on_stale_master_target(
    initialised_db: str, caplog: pytest.LogCaptureFixture
) -> None:
    with Session(get_engine()) as session:
        # A master target frozen 60 days ago → staleness must alert.
        _seed_target(
            session,
            "master_portfolio",
            _AS_OF - timedelta(days=60),
            [
                {"symbol": "SGOV", "sleeve": "master", "target_weight": 0.44},
                {"symbol": "SPY", "sleeve": "momentum", "target_weight": 0.56},
            ],
        )
        session.commit()

        with caplog.at_level(logging.WARNING):
            run_monitoring(session, as_of=_AS_OF)
            session.commit()

        metrics = MonitoringMetricRepository(session).latest_by_metric("master_portfolio")
        staleness = metrics["target_staleness_days"]
        assert staleness.value == 60.0
        assert staleness.meta["is_stale"] is True
        # The cash-parked share is surfaced (SGOV 44%).
        assert metrics["sleeve_cash_pct"].value == pytest.approx(0.44)
        # A warning fires so the timer journal shows the freeze.
        assert "monitoring_target_stale" in caplog.text


def test_run_monitoring_marks_fresh_regime_target_not_stale(
    initialised_db: str, caplog: pytest.LogCaptureFixture
) -> None:
    with Session(get_engine()) as session:
        _seed_target(
            session,
            "regime_adaptive",
            _AS_OF - timedelta(days=5),
            [{"symbol": "SPY", "sleeve": "regime", "target_weight": 1.0}],
        )
        session.commit()

        with caplog.at_level(logging.WARNING):
            run_monitoring(session, as_of=_AS_OF)
            session.commit()

        # The per-strategy metric is the precise, non-confounded signal: a fresh
        # target is NOT stale (a global caplog check would trip on the OTHER
        # monitored strategies that have no seeded target — an absent target is a
        # freeze too, so they legitimately alert).
        metrics = MonitoringMetricRepository(session).latest_by_metric("regime_adaptive")
        assert metrics["target_staleness_days"].value == 5.0
        assert metrics["target_staleness_days"].meta["is_stale"] is False
        regime_alerts = [
            r
            for r in caplog.records
            if r.msg == "monitoring_target_stale"
            and getattr(r, "strategy_id", None) == "regime_adaptive"
        ]
        assert not regime_alerts
