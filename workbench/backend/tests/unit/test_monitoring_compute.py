"""B080 F002 — pure monitoring compute (IC / exposure / tracking) + metric store."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.monitoring_metric import MonitoringMetricRepository
from workbench_api.monitoring.exposure import exposure_metrics, pit_universe_caps
from workbench_api.monitoring.ic import (
    forward_returns,
    holdings_ic_for_date,
    rank_ic,
    rolling_ic,
)
from workbench_api.monitoring.tracking import tracking_error, turnover_metrics

_D = date


# --------------------------------------------------------------------------- #
# IC
# --------------------------------------------------------------------------- #


def test_forward_returns_no_lookahead_and_runs_out() -> None:
    dates = [_D(2026, 1, i) for i in range(1, 11)]
    closes = [float(x) for x in range(10, 20)]  # 10..19
    # event on day 3 → entry is first day STRICTLY after (index 3 = day 4, close 13).
    out = forward_returns((dates, closes), _D(2026, 1, 3), (5,))
    assert out[5] == closes[3 + 5] / closes[3] - 1.0
    # horizon that runs past the series → None (position could not be held).
    assert forward_returns((dates, closes), _D(2026, 1, 8), (5,))[5] is None


def test_rank_ic_perfect_inverse_degenerate() -> None:
    assert rank_ic([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert rank_ic([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0
    assert rank_ic([1, 1, 1], [1, 2, 3]) is None  # no variance in signals
    assert rank_ic([1], [1]) is None  # < 2 pairs


def test_holdings_ic_for_date_uses_forward_returns() -> None:
    # Two names; heavier-weighted name has the higher forward return → IC = 1.
    dates = [_D(2026, 1, i) for i in range(1, 30)]
    up = [1.0 + 0.01 * i for i in range(29)]  # rising
    flat = [1.0 for _ in range(29)]
    price = {"AAA": (dates, up), "BBB": (dates, flat)}
    ic = holdings_ic_for_date([("AAA", 0.7), ("BBB", 0.3)], price, _D(2026, 1, 2), 5)
    assert ic == pytest.approx(1.0)


def test_rolling_ic_partial_flag_and_tstat() -> None:
    as_of = _D(2026, 7, 1)
    # 30 days of history (< 365) → partial True; constant positive IC → t-stat huge.
    dated = [(as_of - timedelta(days=k), 0.1) for k in range(30)]
    out = rolling_ic(dated, as_of)
    assert out["value"] == 0.1
    assert out["meta"]["partial"] is True
    assert out["meta"]["coverage_days"] == 29
    # empty window → None value, no crash.
    assert rolling_ic([], as_of)["value"] is None


# --------------------------------------------------------------------------- #
# exposure
# --------------------------------------------------------------------------- #


def test_pit_universe_caps_takes_latest_on_or_before() -> None:
    rows = [
        (_D(2026, 1, 31), "AAA", 100.0),
        (_D(2026, 2, 28), "AAA", 120.0),  # later, still <= as_of
        (_D(2026, 8, 31), "AAA", 999.0),  # future → excluded
        (_D(2026, 2, 28), "BBB", 50.0),
    ]
    caps = pit_universe_caps(rows, _D(2026, 7, 1))
    assert caps == {"AAA": 120.0, "BBB": 50.0}


def test_exposure_metrics_pctile_smallcap_hhi() -> None:
    universe = {f"S{i}": float(i) for i in range(1, 11)}  # caps 1..10, median 6
    holdings = [("S2", 0.5), ("S9", 0.5)]  # one small, one large; HHI 0.5
    m = exposure_metrics(holdings, universe)
    assert m["exposure_hhi"]["value"] == 0.5
    # one of two holds below the universe median (6) → 0.5
    assert m["exposure_smallcap_frac"]["value"] == 0.5
    assert 0.0 < m["exposure_median_cap_pctile"]["value"] <= 1.0
    # a symbol absent from the cap universe is not counted.
    assert m["exposure_median_cap_pctile"]["meta"]["cap_covered"] == 2


# --------------------------------------------------------------------------- #
# tracking / turnover
# --------------------------------------------------------------------------- #


def test_tracking_error_overlap_and_partial() -> None:
    navs = [(_D(2026, 1, i), 100.0 + i) for i in range(1, 6)]
    bench = [(_D(2026, 1, i), 200.0 + i) for i in range(1, 6)]
    te = tracking_error(navs, bench)
    assert te["value"] is not None and te["value"] >= 0.0
    assert te["meta"]["overlap_days"] == 4
    assert te["meta"]["partial"] is True  # < 20 overlap days
    # < 2 overlapping days → None (honest degrade).
    assert tracking_error(navs[:1], bench)["value"] is None


def test_turnover_metrics_counts_and_freq() -> None:
    rebs = [(_D(2026, 1, 10), 5.0), (_D(2026, 4, 10), 7.0)]
    m = turnover_metrics(rebs, activated_on=_D(2025, 1, 10), as_of=_D(2026, 1, 10))
    assert m["turnover_rebalance_count"]["value"] == 2.0
    assert m["turnover_total_cost"]["value"] == 12.0
    assert m["turnover_total_cost"]["meta"]["avg_cost"] == 6.0
    assert m["turnover_rebalance_freq_yr"]["value"] == 2.0  # 2 over ~1 year


# --------------------------------------------------------------------------- #
# metric store
# --------------------------------------------------------------------------- #


def test_metric_upsert_idempotent_and_latest(initialised_db: str) -> None:
    with Session(get_engine()) as session:
        repo = MonitoringMetricRepository(session)
        stamp = datetime(2026, 7, 1, tzinfo=UTC)
        repo.upsert_metric(
            strategy_id="cn_attack_pure_momentum",
            as_of=_D(2026, 7, 1),
            metric="rolling_ic_5",
            value=0.08,
            meta={"partial": True},
            computed_at=stamp,
        )
        session.commit()
        # Same natural key → replace in place, not a second row.
        repo.upsert_metric(
            strategy_id="cn_attack_pure_momentum",
            as_of=_D(2026, 7, 1),
            metric="rolling_ic_5",
            value=0.09,
            meta={"partial": False},
            computed_at=stamp,
        )
        session.commit()
        assert repo.count() == 1
        latest = repo.latest_by_metric("cn_attack_pure_momentum")
        assert latest["rolling_ic_5"].value == 0.09
        assert latest["rolling_ic_5"].meta == {"partial": False}
