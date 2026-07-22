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

from workbench_api.data_refresh.freshness import latest_recommendation_as_of
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
from workbench_api.monitoring.staleness import assess_target_staleness
from workbench_api.monitoring.tracking import (
    STRATEGY_BENCHMARK,
    tracking_error,
    turnover_metrics,
)

logger = logging.getLogger(__name__)

# The synthetic cash row the CN modes persist — never part of an IC/exposure cross-section.
CASH_SYMBOL = "CASH"

# Cash / defensive symbols across the funded USD accounts + the CN synthetic cash
# row — their combined weight is a sleeve's "parked in cash" share (P0-3: the
# regime/us_quality/hk_china sleeves silently sat 44-55% in SGOV).
_CASH_SYMBOLS = frozenset({"SGOV", "BIL", "SHY", CASH_SYMBOL})


def monitored_strategy_ids() -> tuple[str, ...]:
    """The strategies this monitoring job covers, derived from the registry.

    The CSI300-benchmarked CN research cohort (IC + paper metrics) PLUS the
    USD accounts ``master_portfolio`` and ``regime_adaptive`` (B111 F003). Those
    two were previously excluded — that exclusion is exactly why the three P0s
    (frozen regime target, poisoned us_quality sleeve, momentum data bug) ran for
    7 weeks with zero alerts. They now get the staleness + sleeve-cash metrics
    (``_account_health_metrics``) that would have caught the freeze; the IC /
    paper-tracking metrics still degrade to a no-op when their CN-shaped inputs
    are absent. Registry selector order is preserved (the CN modes first), so the
    existing CN cohort stays byte-identical and master/regime append after.
    """

    from workbench_api.strategy_modes.registry import (
        MASTER_STRATEGY_ID,
        REGIME_STRATEGY_ID,
        list_modes,
    )

    cn_cohort = tuple(
        mode.strategy_id
        for mode in list_modes()
        if mode.is_research_state
        and STRATEGY_BENCHMARK.get(mode.strategy_id) == "CSI300"
    )
    return (*cn_cohort, MASTER_STRATEGY_ID, REGIME_STRATEGY_ID)


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


def _account_health_metrics(
    session: Session,
    metric_repo: MonitoringMetricRepository,
    strategy_id: str,
    as_of: date,
    computed_at: datetime,
) -> int:
    """B111 F003 (P0-3) — target staleness, sleeve-cash %, and NAV drawdown.

    These are precisely the signals whose ABSENCE let the three P0s run for 7
    weeks: a published target that stopped advancing (staleness → alert), a
    sleeve parked 100% in cash (cash %), and account drawdown. Each degrades to a
    skipped metric when its input is absent; the staleness metric emits a WARNING
    the timer's journal surfaces when the target is stale (> 45 days)."""

    written = 0

    # 1) Target staleness — the P0-3 frozen-target detector, with an alert.
    published_as_of = latest_recommendation_as_of(session, strategy_id)
    verdict = assess_target_staleness(strategy_id, published_as_of, as_of)
    metric_repo.upsert_metric(
        strategy_id=strategy_id, as_of=as_of, metric="target_staleness_days",
        value=(float(verdict.age_days) if verdict.age_days is not None else None),
        meta={
            "is_stale": verdict.is_stale,
            "threshold_days": verdict.threshold_days,
            "as_of_published": published_as_of.isoformat() if published_as_of else None,
            "reason": verdict.reason,
        },
        computed_at=computed_at,
    )
    written += 1
    if verdict.is_stale:
        logger.warning(
            "monitoring_target_stale",
            extra={
                "strategy_id": strategy_id,
                "age_days": verdict.age_days,
                "threshold_days": verdict.threshold_days,
                "as_of_published": published_as_of.isoformat() if published_as_of else None,
            },
        )

    # 2) Sleeve cash % from the latest published target (44-55% SGOV was the P0 tell).
    rows = RecommendationSnapshotRepository(session).latest_snapshot(strategy_id)
    if rows:
        cash_pct = sum(
            float(r.target_weight) for r in rows if r.symbol in _CASH_SYMBOLS
        )
        metric_repo.upsert_metric(
            strategy_id=strategy_id, as_of=as_of, metric="sleeve_cash_pct",
            value=cash_pct,
            meta={
                "cash_symbols": sorted({r.symbol for r in rows if r.symbol in _CASH_SYMBOLS}),
                "n_positions": len(rows),
            },
            computed_at=computed_at,
        )
        written += 1

    # 3) NAV drawdown vs peak (when the account has a NAV history).
    account = PaperAccountRepository(session).get_by_strategy(strategy_id)
    if account is not None:
        navs = [
            float(n.nav)
            for n in sorted(
                PaperNavHistoryRepository(session).list_by_account(account.id),
                key=lambda n: n.as_of_date,
            )
        ]
        if navs:
            peak = max(navs)
            drawdown = (navs[-1] - peak) / peak if peak > 0 else 0.0
            metric_repo.upsert_metric(
                strategy_id=strategy_id, as_of=as_of, metric="nav_drawdown",
                value=drawdown,
                meta={"peak_nav": peak, "current_nav": navs[-1]},
                computed_at=computed_at,
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
    for strategy_id in monitored_strategy_ids():
        try:
            written += _ic_metrics(session, metric_repo, strategy_id, as_of, stamp)
            written += _paper_metrics(
                session, metric_repo, strategy_id, as_of, stamp,
                cn_size_path=cn_size_path, cn_csi300_path=cn_csi300_path,
            )
            written += _account_health_metrics(
                session, metric_repo, strategy_id, as_of, stamp
            )
        except Exception:  # noqa: BLE001 — one strategy's gap must not fail the job
            logger.warning("monitoring_metrics_failed", extra={"strategy_id": strategy_id})
    return written
