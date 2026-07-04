"""B080 F002 — run_monitoring orchestration (seeded DB → monitoring_metric rows).

Seeds a cn_attack snapshot history + price series + a paper account (nav/rebalances)
+ temp cn_size/cn_csi300 CSVs, runs the job, and asserts the rolling-IC (holdings
fidelity, partial), turnover, exposure, and tracking metrics all land.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session

from workbench_api.db.engine import get_engine
from workbench_api.db.models.paper_account import PaperAccount, PaperRebalance
from workbench_api.db.models.paper_nav_history import PaperNavHistory
from workbench_api.db.repositories.monitoring_metric import MonitoringMetricRepository
from workbench_api.db.repositories.price_history import PriceHistoryRepository
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.monitoring.metrics_job import run_monitoring

_SID = "cn_attack_pure_momentum"
_AS_OF = date(2026, 6, 30)


def _seed(session: Session, size_csv: Path, csi_csv: Path) -> None:
    # 30 daily closes: AAA rising, BBB flat.
    price = PriceHistoryRepository(session)
    day0 = date(2026, 6, 1)
    for k in range(30):
        d = day0 + timedelta(days=k)
        price.save_if_new(symbol="AAA", obs_date=d, close=100.0 + k, source="test")
        price.save_if_new(symbol="BBB", obs_date=d, close=50.0, source="test")

    # Two snapshot dates: AAA over-weighted vs BBB (+ CASH), weights sum to 1.0.
    rec = RecommendationSnapshotRepository(session)
    for d in (date(2026, 6, 2), date(2026, 6, 3)):
        rec.save_batch(
            as_of_date=d,
            strategy_id=_SID,
            master_meta={"data_source": "test"},
            rows=[
                {"symbol": "AAA", "sleeve": "cn_attack", "target_weight": 0.6},
                {"symbol": "BBB", "sleeve": "cn_attack", "target_weight": 0.3},
                {"symbol": "CASH", "sleeve": "cash", "target_weight": 0.1},
            ],
        )

    # Paper account + nav history (SPY benchmark_close) + rebalances.
    _now = datetime(2026, 6, 30, tzinfo=UTC)
    acct = PaperAccount(
        id="pa-cnattack", strategy_id=_SID, initial_capital=100000.0, cash=1000.0,
        base_currency="CNY", fee_bps=2.5, slippage_bps=10.0, activated_on=date(2025, 6, 30),
        created_at=_now, updated_at=_now,
    )
    session.add(acct)
    for k in range(5):
        d = date(2026, 6, 26) + timedelta(days=k)
        session.add(
            PaperNavHistory(
                id=f"nav-{k}", account_id=acct.id, as_of_date=d, nav=100000.0 + 100 * k,
                cash=1000.0,
                positions=[
                    {"symbol": "AAA", "market_value": 60000.0},
                    {"symbol": "BBB", "market_value": 40000.0},
                ],
                benchmark_close=400.0 + k, created_at=_now,
            )
        )
    for k in range(2):
        session.add(
            PaperRebalance(
                id=f"reb-{k}", account_id=acct.id,
                rebalance_date=date(2026, 3, 1) + timedelta(days=90 * k), cost=5.0 + k,
                target_key=f"tk{k}", created_at=datetime(2026, 6, 30, tzinfo=UTC),
            )
        )
    session.commit()

    size_csv.write_text(
        "data_date,ticker,market_cap\n"
        "2026-05-31,AAA,9000000000\n2026-05-31,BBB,1000000000\n"
        "2026-05-31,CCC,5000000000\n2026-05-31,DDD,3000000000\n",
        encoding="utf-8",
    )
    csi_csv.write_text(
        "date,close\n" + "".join(
            f"{(date(2026,6,26)+timedelta(days=k)).isoformat()},{3800.0+k}\n" for k in range(5)
        ),
        encoding="utf-8",
    )


def test_run_monitoring_writes_all_metric_families(initialised_db: str, tmp_path: Path) -> None:
    size_csv = tmp_path / "cn_size.csv"
    csi_csv = tmp_path / "cn_csi300.csv"
    with Session(get_engine()) as session:
        _seed(session, size_csv, csi_csv)
        written = run_monitoring(
            session, as_of=_AS_OF, cn_size_path=size_csv, cn_csi300_path=csi_csv
        )
        session.commit()
        assert written > 0

        metrics = MonitoringMetricRepository(session).latest_by_metric(_SID)
        # Rolling holdings-IC per horizon, flagged partial + holdings-fidelity.
        for n in (5, 10, 20):
            row = metrics[f"rolling_ic_{n}"]
            assert row.meta["fidelity"] == "holdings"
            assert row.meta["partial"] is True
        assert metrics["rolling_ic_5"].value is not None  # AAA weight ranks with its rising return
        # Turnover from the two rebalances.
        assert metrics["turnover_rebalance_count"].value == 2.0
        assert metrics["turnover_total_cost"].value == 11.0
        # Exposure + tracking landed (CSI300 benchmark for cn_attack).
        assert "exposure_hhi" in metrics
        assert metrics["tracking_error"].meta["benchmark"] == "CSI300"
