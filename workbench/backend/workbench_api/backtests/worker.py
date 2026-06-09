"""B047 F002 — on-demand async backtest worker daemon.

Long-running loop: claim the oldest queued ``backtest_run`` → run the REAL
``trade`` Master Portfolio backtest engine + report generation → write the
result (or error) back to the DB. Polls with a short sleep when the queue is
empty (low-latency pickup without an async runtime).

§12.10.2: this worker (off the request path) is the allowed importer of
``trade``. Boundary (r): deterministic backtest over read-only price data —
no broker / order-ticket / execution.

Data source: the B045 **unified daily** real prices (``WORKBENCH_DATA_ROOT``
on the VM). The Master backtest needs daily history — the bundled monthly ETF
fixture cannot drive risk_parity's 60-day vol window — so when the unified CSV
is absent (local / CI without a data-refresh) the run fails gracefully with an
honest "data unavailable" error rather than a fabricated result. Running the
real engine on real daily data is a REAL backtest (vs the old synthetic hash
stub).

Run as: ``python -m workbench_api.backtests.worker`` (systemd
``workbench-backtest-worker.service``).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Callable
from datetime import date
from typing import Any, Protocol

from sqlalchemy.orm import Session, sessionmaker

from workbench_api.backtests.adapters import (
    adapt_momentum,
    adapt_risk_parity,
    adapt_us_quality,
)
from workbench_api.backtests.error_kinds import classify_error_kind
from workbench_api.backtests.explanation import generate_backtest_explanation
from workbench_api.backtests.mapping import (
    map_allocations,
    map_equity,
    map_metrics,
    map_trades,
)
from workbench_api.db.engine import get_engine
from workbench_api.services.explanation import (
    ExplanationService,
    build_default_explainer,
)
from workbench_api.db.repositories.backtest_run import BacktestRunRepository
from workbench_api.db.require_production_db import (
    ScratchDatabaseError,
    require_production_db,
)

logger = logging.getLogger(__name__)


class BacktestRunLike(Protocol):
    """Structural view of a queued run the engine needs — a ``BacktestRun``
    row, or the canonical job's lightweight stand-in.

    B050 F001: ``strategy_id`` (already a ``backtest_run`` column) is read to
    dispatch to the right engine. The canonical stand-in sets it explicitly to
    ``"master_portfolio"``; ``run_backtest_job`` also defaults a missing value to
    master so an older stand-in never breaks."""

    run_id: str
    strategy_id: str
    params: dict[str, Any] | None

POLL_SECONDS = float(os.environ.get("WORKBENCH_BACKTEST_POLL_SECONDS", "3.0"))

# B050 F001 — Master Portfolio is the default / fallback strategy_id (the
# canonical report job + any stand-in without a strategy_id resolve to it).
MASTER_STRATEGY_ID = "master_portfolio"

# B050 F001 — regime overlays ship research-state at planning_weight 0.0; they
# have no standalone backtest, so the worker excludes them with a structured
# error_kind (the frontend maps it to a bilingual "not supported" message)
# instead of silently running master.
INACTIVE_STRATEGY_IDS = frozenset(
    {"B013-regime-quarterly", "B014-regime-stress", "B015-regime-active"}
)


class BacktestWorkerError(RuntimeError):
    """A backtest run could not be executed (mapped to the run's ``error``)."""


class InactiveStrategyError(BacktestWorkerError):
    """The requested strategy is research-state (planning_weight 0.0) and has no
    standalone backtest — surfaced to the user as ``error_kind=inactive_strategy``."""


def _parse_iso(value: object) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _signal_dates_in_range(
    quarter_ends: tuple[date, ...], params: dict[str, Any]
) -> tuple[date, ...]:
    """Quarter-end signal dates within the request's [start, end] window
    (inclusive). An absent / unparseable bound does not filter that side."""

    start = _parse_iso(params.get("start_date"))
    end = _parse_iso(params.get("end_date"))
    return tuple(
        d
        for d in quarter_ends
        if (start is None or d >= start) and (end is None or d <= end)
    )


def _monthly_signal_dates(
    all_dates: tuple[date, ...], params: dict[str, Any]
) -> tuple[date, ...]:
    """Last trading day of each month within the request's [start, end] window.

    Reuses ``trade.analysis.parameter_sweep.build_monthly_signal_dates`` (the
    canonical month-end builder) so the monthly engines (momentum / risk_parity)
    rebalance on the same cadence the rest of the package uses. Absent bounds
    default to the full data range."""

    from trade.analysis.parameter_sweep import (  # type: ignore[import-untyped]
        build_monthly_signal_dates,
    )

    if not all_dates:
        return ()
    start = _parse_iso(params.get("start_date")) or all_dates[0]
    end = _parse_iso(params.get("end_date")) or all_dates[-1]
    return tuple(build_monthly_signal_dates(all_dates, start, end))


def _strategy_parameters(strategy_id: str, run: BacktestRunLike, param_type: Any) -> Any:
    """Build a strategy ``Parameters`` object from ``run.params["parameters"]``.

    An empty / absent override → ``None`` so the engine uses its locked defaults
    (the current behaviour — the frontend has no parameter editor yet). A
    non-empty override is constructed into the strategy's ``Parameters`` type;
    bad keys surface as a clear ``BacktestWorkerError`` rather than a 500."""

    raw = (run.params or {}).get("parameters") or {}
    if not raw:
        return None
    try:
        return param_type(**raw)
    except (TypeError, ValueError) as exc:
        raise BacktestWorkerError(
            f"invalid parameters for strategy {strategy_id}: {exc}"
        ) from exc


def _drop_earliest_retry(
    run_fn: Callable[[tuple[date, ...]], Any],
    signal_dates: tuple[date, ...],
    lookback_errors: tuple[type[BaseException], ...],
) -> Any:
    """Run ``run_fn(signal_dates)``, dropping the earliest signal date and
    retrying while the engine raises a lookback-shortfall error.

    The earliest signal dates may lack the lookback the sleeves need; dropping
    them lets the backtest span whatever the data supports rather than failing
    outright (B047 behaviour, now shared across the dispatched engines)."""

    usable = list(signal_dates)
    while True:
        try:
            return run_fn(tuple(usable))
        except lookback_errors as exc:
            if len(usable) <= 1:
                raise BacktestWorkerError(
                    f"insufficient price history for any signal date in range: {exc}"
                ) from exc
            usable = usable[1:]


def _load_backtest_snapshot() -> Any:
    """Build a ``DataSnapshot`` from the B045 unified **daily** real prices.

    The Master backtest needs daily history (risk_parity's 60-day vol window,
    momentum's multi-month windows) — the bundled monthly ETF fixture can't run
    it with default params. So the worker requires the unified real-data CSV
    (present on the VM after a data-refresh). When it is absent (local / CI
    without a refresh) the run fails gracefully → the request surfaces an
    honest "backtest data unavailable" error rather than a fabricated result."""

    import hashlib
    from datetime import date

    from trade.data.data_root import (  # type: ignore[import-untyped]
        data_root_override,
        unified_prices_path,
    )
    from trade.data.loader import (  # type: ignore[import-untyped]
        UNIFIED_PRICES_PATH,
        DataSnapshot,
        load_prices,
    )

    from workbench_api.data_refresh.refresh import price_universe

    if data_root_override() is None or not unified_prices_path(UNIFIED_PRICES_PATH).exists():
        raise BacktestWorkerError(
            "no real price data available (unified daily CSV absent); run the "
            "data-refresh job first — the monthly fixture cannot drive the "
            "Master backtest"
        )
    by_ticker = load_prices(list(price_universe()), date.today())
    records = tuple(bar for bars in by_ticker.values() for bar in bars)
    if not records:
        raise BacktestWorkerError("unified price data yielded no rows")

    symbols = tuple(sorted({r.symbol for r in records}))
    dates = sorted({r.date for r in records})
    checksum = hashlib.sha256(
        "\n".join(
            f"{r.symbol}|{r.date.isoformat()}|{r.close}|{r.adjusted_close}"
            for r in records
        ).encode("utf-8")
    ).hexdigest()
    return DataSnapshot(
        records=records,
        source="b045_unified_real",
        adjusted_price_policy="adjusted_close",
        data_snapshot_id=f"unified:{checksum[:16]}",
        checksum=checksum,
        start_date=dates[0],
        end_date=dates[-1],
        symbols=symbols,
        trading_calendar_gaps=(),
    )


def _run_master(snapshot: Any, run: BacktestRunLike) -> dict[str, Any]:
    """Master Portfolio (quarterly) — the existing real-engine path."""

    from trade.backtest.master_portfolio import (  # type: ignore[import-untyped]
        identify_quarter_end_signal_dates,
        run_master_portfolio_quarterly_backtest,
    )
    from trade.reporting.master_portfolio import (  # type: ignore[import-untyped]
        build_master_portfolio_report_payload,
        render_master_portfolio_markdown,
    )
    from trade.strategies.global_etf_momentum import (  # type: ignore[import-untyped]
        MomentumSignalError,
    )
    from trade.strategies.risk_parity import (  # type: ignore[import-untyped]
        RiskParityDataError,
    )

    records = snapshot.records
    all_dates = tuple(sorted({record.date for record in records}))
    quarter_ends = identify_quarter_end_signal_dates(all_dates)
    signal_dates = _signal_dates_in_range(quarter_ends, run.params or {})
    if not signal_dates:
        raise BacktestWorkerError(
            "no quarter-end signal dates available in the requested date range"
        )
    result = _drop_earliest_retry(
        lambda usable: run_master_portfolio_quarterly_backtest(records, usable),
        signal_dates,
        (MomentumSignalError, RiskParityDataError),
    )
    payload = build_master_portfolio_report_payload(result, snapshot, run.run_id)
    return {
        "metrics": map_metrics(payload),
        "equity": map_equity(result),
        "allocations": map_allocations(result),
        "trades": map_trades(result),
        "report_markdown": render_master_portfolio_markdown(payload),
    }


def _run_momentum(snapshot: Any, run: BacktestRunLike) -> dict[str, Any]:
    """Global ETF Momentum (monthly) — ``run_multi_monthly_backtest``."""

    from trade.backtest.monthly import (  # type: ignore[import-untyped]
        run_multi_monthly_backtest,
    )
    from trade.reporting.reports import (  # type: ignore[import-untyped]
        build_report_payload,
        render_markdown_report,
    )
    from trade.strategies.global_etf_momentum import (
        MomentumParameters,
        MomentumSignalError,
    )

    records = snapshot.records
    all_dates = tuple(sorted({record.date for record in records}))
    signal_dates = _monthly_signal_dates(all_dates, run.params or {})
    if not signal_dates:
        raise BacktestWorkerError(
            "no monthly signal dates available in the requested date range"
        )
    params = _strategy_parameters("B006-global-etf-momentum", run, MomentumParameters)
    result = _drop_earliest_retry(
        lambda usable: run_multi_monthly_backtest(
            records, usable, strategy_parameters=params
        ),
        signal_dates,
        (MomentumSignalError,),
    )
    payload = build_report_payload(result, snapshot, run.run_id)
    return {
        "metrics": map_metrics(payload),
        **adapt_momentum(result),
        "report_markdown": render_markdown_report(payload),
    }


def _run_risk_parity(snapshot: Any, run: BacktestRunLike) -> dict[str, Any]:
    """Risk Parity (monthly) — ``run_risk_parity_monthly_backtest``.

    Runs with the engine's locked defaults (inverse-volatility weighting); the
    HRP weighting the B016 registry name references is a parameter not yet wired
    from the UI (no parameter editor) — it would flow through ``_strategy_parameters``
    when a future override is sent."""

    from trade.backtest.risk_parity import (  # type: ignore[import-untyped]
        run_risk_parity_monthly_backtest,
    )
    from trade.reporting.risk_parity import (  # type: ignore[import-untyped]
        build_risk_parity_report_payload,
        render_risk_parity_markdown,
    )
    from trade.strategies.risk_parity import (
        RiskParityDataError,
        RiskParityParameters,
    )

    records = snapshot.records
    all_dates = tuple(sorted({record.date for record in records}))
    signal_dates = _monthly_signal_dates(all_dates, run.params or {})
    if not signal_dates:
        raise BacktestWorkerError(
            "no monthly signal dates available in the requested date range"
        )
    params = _strategy_parameters("B016-risk-parity-hrp", run, RiskParityParameters)
    result = _drop_earliest_retry(
        lambda usable: run_risk_parity_monthly_backtest(
            records, usable, strategy_parameters=params
        ),
        signal_dates,
        (RiskParityDataError,),
    )
    payload = build_risk_parity_report_payload(result, snapshot, run.run_id)
    return {
        "metrics": map_metrics(payload),
        **adapt_risk_parity(result),
        "report_markdown": render_risk_parity_markdown(payload),
    }


def _run_us_quality(snapshot: Any, run: BacktestRunLike) -> dict[str, Any]:
    """US Quality Momentum (monthly) — ``us_quality_momentum.engine.run_backtest``.

    Unlike the records-based engines this one loads its own universe / prices /
    fundamentals internally and takes ``start`` / ``end`` directly (not
    ``records`` + ``signal_dates``); its equity curve is a daily ``pd.DataFrame``
    and it reports no per-leg fills (the adapter surfaces empty trades)."""

    from trade.backtest.us_quality_momentum.engine import (  # type: ignore[import-untyped]
        run_backtest,
    )
    from trade.reporting.us_quality_momentum import (  # type: ignore[import-untyped]
        build_us_quality_report_payload,
        render_us_quality_markdown,
    )
    from trade.strategies.us_quality_momentum.parameters import (  # type: ignore[import-untyped]
        UsQualityMomentumParameters,
    )

    params = _strategy_parameters(
        "B025-us-quality-momentum", run, UsQualityMomentumParameters
    )
    request = run.params or {}
    result = run_backtest(
        parameters=params,
        start=_parse_iso(request.get("start_date")),
        end=_parse_iso(request.get("end_date")),
    )
    payload = build_us_quality_report_payload(result, snapshot, run.run_id)
    return {
        "metrics": map_metrics(payload),
        **adapt_us_quality(result),
        "report_markdown": render_us_quality_markdown(payload),
    }


def _run_hk_china(snapshot: Any, run: BacktestRunLike) -> dict[str, Any]:
    """HK-China Momentum (quarterly) — the B050 F003 standalone engine.

    Quarterly cadence (matches the sleeve's config inside the Master); reuses the
    shared ``generate_hk_china_signal`` (same source as the Master sleeve) and a
    risk_parity-isomorphic result, so ``adapt_risk_parity`` maps it."""

    from trade.backtest.hk_china import (  # type: ignore[import-untyped]
        run_hk_china_quarterly_backtest,
    )
    from trade.backtest.master_portfolio import identify_quarter_end_signal_dates
    from trade.reporting.hk_china import (  # type: ignore[import-untyped]
        build_hk_china_report_payload,
        render_hk_china_markdown,
    )
    from trade.strategies.hk_china_momentum.parameters import (  # type: ignore[import-untyped]
        HkChinaMomentumParameters,
    )

    records = snapshot.records
    all_dates = tuple(sorted({record.date for record in records}))
    quarter_ends = identify_quarter_end_signal_dates(all_dates)
    signal_dates = _signal_dates_in_range(quarter_ends, run.params or {})
    if not signal_dates:
        raise BacktestWorkerError(
            "no quarter-end signal dates available in the requested date range"
        )
    params = _strategy_parameters(
        "B011-satellite-hk-china", run, HkChinaMomentumParameters
    )
    result = _drop_earliest_retry(
        lambda usable: run_hk_china_quarterly_backtest(
            records, usable, strategy_parameters=params
        ),
        signal_dates,
        (KeyError,),
    )
    payload = build_hk_china_report_payload(result, snapshot, run.run_id)
    return {
        "metrics": map_metrics(payload),
        **adapt_risk_parity(result),
        "report_markdown": render_hk_china_markdown(payload),
    }


# B050 — strategy_id → engine runner. F001 Tier-1 (master / momentum /
# risk_parity); F002 us_quality; F003 hk_china (standalone engine).
_DISPATCH: dict[str, Callable[[Any, BacktestRunLike], dict[str, Any]]] = {
    MASTER_STRATEGY_ID: _run_master,
    "B006-global-etf-momentum": _run_momentum,
    "B016-risk-parity-hrp": _run_risk_parity,
    "B025-us-quality-momentum": _run_us_quality,
    "B011-satellite-hk-china": _run_hk_china,
}


def run_backtest_job(
    run: BacktestRunLike, explainer: ExplanationService | None = None
) -> dict[str, Any]:
    """Run the backtest for one queued run, dispatched by ``strategy_id``.

    Reads ``run.strategy_id`` (a ``backtest_run`` column), looks up the engine in
    ``_DISPATCH`` and returns the mapped result + report markdown. Imports
    ``trade`` lazily inside each runner so the module loads without the heavy
    stack (and so the §12.10.2 AST guard scans the imports here, the allowed
    location). A missing ``strategy_id`` defaults to master (the canonical
    stand-in); a research-state strategy raises ``InactiveStrategyError``.

    B043 F002: when an ``explainer`` is supplied (the worker daemon builds one),
    a grounded "why these results" ``explanation`` is added to the mapped dict
    from the real metrics; ``None`` explainer (canonical / tests) → no LLM call,
    ``explanation`` is ``None``."""

    strategy_id = getattr(run, "strategy_id", None) or MASTER_STRATEGY_ID
    if strategy_id in INACTIVE_STRATEGY_IDS:
        raise InactiveStrategyError(
            f"strategy {strategy_id} is research-state (planning_weight 0.0) and "
            "has no standalone backtest"
        )
    runner = _DISPATCH.get(strategy_id)
    if runner is None:
        raise BacktestWorkerError(
            f"no backtest engine wired for strategy_id={strategy_id!r}"
        )
    snapshot = _load_backtest_snapshot()
    mapped = runner(snapshot, run)
    mapped["explanation"] = generate_backtest_explanation(explainer, run, mapped)
    return mapped


def process_next(session: Session, explainer: ExplanationService | None = None) -> bool:
    """Claim + process one queued run. Returns ``True`` if a run was handled
    (so the caller skips the idle sleep), ``False`` when the queue was empty.

    A run that fails the engine is marked ``error`` (never crashes the loop)."""

    repo = BacktestRunRepository(session)
    run = repo.claim_next_queued()
    if run is None:
        return False
    # Persist the `running` claim before the (heavy) engine call so a crash
    # mid-backtest leaves a visible `running` row, not a lost `queued` one.
    session.commit()
    run_id = run.run_id
    try:
        mapped = run_backtest_job(run, explainer)
    except Exception as exc:  # noqa: BLE001 — any engine failure → error state
        logger.exception("backtest_worker_run_failed", extra={"run_id": run_id})
        session.rollback()
        repo.save_error(
            run_id,
            f"{type(exc).__name__}: {exc}",
            error_kind=classify_error_kind(exc),
        )
        session.commit()
        return True
    repo.save_result(
        run_id,
        metrics=mapped["metrics"],
        equity=mapped["equity"],
        allocations=mapped["allocations"],
        trades=mapped["trades"],
        report_markdown=mapped["report_markdown"],
        explanation=mapped.get("explanation"),
    )
    session.commit()
    logger.info("backtest_worker_run_done", extra={"run_id": run_id})
    return True


def main(*, poll_seconds: float = POLL_SECONDS, max_iterations: int | None = None) -> int:
    """Run the poll loop. ``max_iterations`` bounds the loop for tests; the
    daemon runs unbounded (``None``)."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    # B047-OPS1 F001 — hard-fail before opening a session if WORKBENCH_DB_URL is
    # unset (the daemon would drain the queue into the dev scratch DB, not prod).
    # Loud non-zero exit, no DB write.
    try:
        require_production_db(entrypoint="worker")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    # B043 F002: build the LLM explainer once (None on a host without the gateway
    # key → backtests run with explanation=None, no LLM call).
    explainer = build_default_explainer()
    iterations = 0
    logger.info("backtest_worker_started", extra={"poll_seconds": poll_seconds})
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        session = factory()
        try:
            handled = process_next(session, explainer)
        except Exception:  # noqa: BLE001 — never let the daemon die on a DB blip
            logger.exception("backtest_worker_loop_error")
            session.rollback()
            handled = False
        finally:
            session.close()
        if not handled:
            time.sleep(poll_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
