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
import time
from datetime import date
from typing import Any, Protocol

from sqlalchemy.orm import Session, sessionmaker

from workbench_api.backtests.mapping import (
    map_allocations,
    map_equity,
    map_metrics,
    map_trades,
)
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.backtest_run import BacktestRunRepository

logger = logging.getLogger(__name__)


class BacktestRunLike(Protocol):
    """Structural view of a queued run the engine needs — a ``BacktestRun``
    row, or the canonical job's lightweight stand-in."""

    run_id: str
    params: dict[str, Any] | None

POLL_SECONDS = float(os.environ.get("WORKBENCH_BACKTEST_POLL_SECONDS", "3.0"))


class BacktestWorkerError(RuntimeError):
    """A backtest run could not be executed (mapped to the run's ``error``)."""


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


def run_backtest_job(run: BacktestRunLike) -> dict[str, Any]:
    """Run the real Master Portfolio backtest for one queued run and return
    the mapped result + report markdown. Imports ``trade`` lazily so the
    module loads without the heavy stack (and so the AST guard scans the
    import here, the allowed location)."""

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

    snapshot = _load_backtest_snapshot()
    records = snapshot.records
    all_dates = tuple(sorted({record.date for record in records}))
    quarter_ends = identify_quarter_end_signal_dates(all_dates)
    signal_dates = _signal_dates_in_range(quarter_ends, run.params or {})
    if not signal_dates:
        raise BacktestWorkerError(
            "no quarter-end signal dates available in the requested date range"
        )

    # The earliest quarter-ends may lack the lookback the momentum / risk-parity
    # sleeves need (always true for the monthly fixture; never for the VM's daily
    # unified data). Drop the earliest signal date and retry until the window is
    # satisfied, so the backtest spans whatever the data supports rather than
    # failing outright.
    usable = list(signal_dates)
    while True:
        try:
            result = run_master_portfolio_quarterly_backtest(records, tuple(usable))
            break
        except (MomentumSignalError, RiskParityDataError) as exc:
            if len(usable) <= 1:
                raise BacktestWorkerError(
                    "insufficient price history for any signal date in range: "
                    f"{exc}"
                ) from exc
            usable = usable[1:]
    payload = build_master_portfolio_report_payload(result, snapshot, run.run_id)
    return {
        "metrics": map_metrics(payload),
        "equity": map_equity(result),
        "allocations": map_allocations(result),
        "trades": map_trades(result),
        "report_markdown": render_master_portfolio_markdown(payload),
    }


def process_next(session: Session) -> bool:
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
        mapped = run_backtest_job(run)
    except Exception as exc:  # noqa: BLE001 — any engine failure → error state
        logger.exception("backtest_worker_run_failed", extra={"run_id": run_id})
        session.rollback()
        repo.save_error(run_id, f"{type(exc).__name__}: {exc}")
        session.commit()
        return True
    repo.save_result(
        run_id,
        metrics=mapped["metrics"],
        equity=mapped["equity"],
        allocations=mapped["allocations"],
        trades=mapped["trades"],
        report_markdown=mapped["report_markdown"],
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
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    iterations = 0
    logger.info("backtest_worker_started", extra={"poll_seconds": poll_seconds})
    while max_iterations is None or iterations < max_iterations:
        iterations += 1
        session = factory()
        try:
            handled = process_next(session)
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
