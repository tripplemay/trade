"""B080 F002 — monitoring metrics orchestration (the weekly job's core).

Reads DB (recommendation_snapshot / paper_* / price_history) + two optional CSVs
(cn_csi300 benchmark, cn_size PIT market caps) and upserts L0 metrics into
``monitoring_metric`` for the two cn_attack research modes: holdings-level rolling
rank-IC (N in {5,10,20}), paper-vs-benchmark tracking error, turnover, and market-cap
exposure / crowding. Every metric is advisory-only observation. Data-absent paths
degrade honestly (metric skipped or ``value=None`` with a ``meta`` flag) rather than
raising, so the timer never wedges. Testable: the caller passes a Session + explicit
CSV paths.
"""

from __future__ import annotations

import csv
import logging
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from workbench_api.db.repositories.monitoring_metric import MonitoringMetricRepository
from workbench_api.db.repositories.paper_account import (
    PaperAccountRepository,
    PaperNavHistoryRepository,
    PaperRebalanceRepository,
)
from workbench_api.db.repositories.price_history import PriceHistoryRepository
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.monitoring.exposure import exposure_metrics, pit_universe_caps
from workbench_api.monitoring.ic import (
    HORIZONS,
    holdings_ic_for_date,
    rolling_ic,
)
from workbench_api.monitoring.tracking import (
    STRATEGY_BENCHMARK,
    tracking_error,
    turnover_metrics,
)

logger = logging.getLogger(__name__)

# The two research-state cn_attack modes this job monitors (spec §2 F002).
MONITORED_STRATEGIES = ("cn_attack_quality_momentum", "cn_attack_pure_momentum")
# The synthetic cash row cn_attack persists — never part of an IC/exposure cross-section.
CASH_SYMBOL = "CASH"


def _load_size_rows(path: Path | None) -> list[tuple[date, str, float]]:
    """Parse cn_size.csv (``data_date, ticker, market_cap``); [] when absent."""

    if path is None or not path.is_file():
        return []
    rows: list[tuple[date, str, float]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            try:
                rows.append(
                    (
                        date.fromisoformat(str(r["data_date"])[:10]),
                        str(r["ticker"]).strip(),
                        float(r["market_cap"]),
                    )
                )
            except (KeyError, ValueError):
                continue
    return rows


def _load_benchmark(path: Path | None) -> list[tuple[date, float]]:
    """Parse a ``date, close`` benchmark CSV (cn_csi300); [] when absent."""

    if path is None or not path.is_file():
        return []
    out: list[tuple[date, float]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for r in csv.DictReader(handle):
            try:
                out.append((date.fromisoformat(str(r["date"])[:10]), float(r["close"])))
            except (KeyError, ValueError):
                continue
    return out


def _ic_metrics(
    session: Session,
    metric_repo: MonitoringMetricRepository,
    strategy_id: str,
    as_of: date,
    computed_at: datetime,
) -> int:
    """Holdings-level rolling rank-IC per horizon from the snapshot history."""

    rec_repo = RecommendationSnapshotRepository(session)
    history = rec_repo.history_by_strategy(strategy_id)
    if not history:
        return 0
    # Group holdings per as_of_date (exclude the synthetic CASH row).
    by_date: dict[date, list[tuple[str, float]]] = {}
    symbols: set[str] = set()
    for row in history:
        if row.symbol == CASH_SYMBOL:
            continue
        by_date.setdefault(row.as_of_date, []).append((row.symbol, float(row.target_weight)))
        symbols.add(row.symbol)
    if not by_date:
        return 0
    earliest = min(by_date)
    price_repo = PriceHistoryRepository(session)
    price_series = {
        sym: (
            [d for d, _ in bars],
            [c for _, c in bars],
        )
        for sym in symbols
        if (bars := price_repo.closes_by_symbol_since(sym, earliest))
    }
    written = 0
    for horizon in HORIZONS:
        dated_ics = [
            (d, holdings_ic_for_date(holdings, price_series, d, horizon))
            for d, holdings in sorted(by_date.items())
        ]
        rolling = rolling_ic(dated_ics, as_of)
        meta = {**rolling["meta"], "fidelity": "holdings", "horizon": horizon}
        metric_repo.upsert_metric(
            strategy_id=strategy_id,
            as_of=as_of,
            metric=f"rolling_ic_{horizon}",
            value=rolling["value"],
            meta=meta,
            computed_at=computed_at,
        )
        written += 1
    return written


def _paper_metrics(
    session: Session,
    metric_repo: MonitoringMetricRepository,
    strategy_id: str,
    as_of: date,
    computed_at: datetime,
    *,
    cn_size_path: Path | None,
    cn_csi300_path: Path | None,
) -> int:
    """Tracking error + turnover + exposure/crowding from the paper account."""

    account = PaperAccountRepository(session).get_by_strategy(strategy_id)
    if account is None:
        return 0
    written = 0
    nav_rows = PaperNavHistoryRepository(session).list_by_account(account.id)
    rebs = PaperRebalanceRepository(session).list_by_account(account.id)

    # Turnover (always available once there's a paper account).
    for metric, payload in turnover_metrics(
        [(r.rebalance_date, float(r.cost)) for r in rebs],
        activated_on=account.activated_on,
        as_of=as_of,
    ).items():
        metric_repo.upsert_metric(
            strategy_id=strategy_id, as_of=as_of, metric=metric,
            value=payload["value"], meta=payload["meta"], computed_at=computed_at,
        )
        written += 1

    # Tracking error vs the per-strategy benchmark.
    benchmark_name = STRATEGY_BENCHMARK.get(strategy_id, "SPY")
    navs = [(n.as_of_date, float(n.nav)) for n in nav_rows]
    if benchmark_name == "CSI300":
        benchmark = _load_benchmark(cn_csi300_path)
    else:
        benchmark = [
            (n.as_of_date, float(n.benchmark_close))
            for n in nav_rows
            if n.benchmark_close is not None
        ]
    if benchmark:
        te = tracking_error(navs, benchmark)
        metric_repo.upsert_metric(
            strategy_id=strategy_id, as_of=as_of, metric="tracking_error",
            value=te["value"], meta={**te["meta"], "benchmark": benchmark_name},
            computed_at=computed_at,
        )
        written += 1

    # Exposure / crowding from the latest paper holdings x cn_size PIT frame.
    size_rows = _load_size_rows(cn_size_path)
    if nav_rows and size_rows:
        latest = max(nav_rows, key=lambda n: n.as_of_date)
        nav_val = float(latest.nav)
        holdings = [
            (str(p["symbol"]), float(p.get("market_value") or 0.0) / nav_val)
            for p in (latest.positions or [])
            if str(p.get("symbol")) != CASH_SYMBOL and nav_val > 0
        ]
        universe = pit_universe_caps(size_rows, as_of)
        for metric, payload in exposure_metrics(holdings, universe).items():
            metric_repo.upsert_metric(
                strategy_id=strategy_id, as_of=as_of, metric=metric,
                value=payload["value"], meta=payload["meta"], computed_at=computed_at,
            )
            written += 1
    return written


def run_monitoring(
    session: Session,
    *,
    as_of: date,
    cn_size_path: Path | None = None,
    cn_csi300_path: Path | None = None,
    computed_at: datetime | None = None,
) -> int:
    """Compute + upsert all L0 metrics for the monitored strategies. Returns the
    number of metric rows written. Never raises on a per-strategy data gap — logs
    and continues (advisory job must not wedge the timer)."""

    stamp = computed_at or datetime.now(UTC)
    metric_repo = MonitoringMetricRepository(session)
    written = 0
    for strategy_id in MONITORED_STRATEGIES:
        try:
            written += _ic_metrics(session, metric_repo, strategy_id, as_of, stamp)
            written += _paper_metrics(
                session, metric_repo, strategy_id, as_of, stamp,
                cn_size_path=cn_size_path, cn_csi300_path=cn_csi300_path,
            )
        except Exception:  # noqa: BLE001 — one strategy's gap must not fail the job
            logger.warning("monitoring_metrics_failed", extra={"strategy_id": strategy_id})
    return written
