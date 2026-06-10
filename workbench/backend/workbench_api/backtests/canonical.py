"""B047 F004 — canonical investment report generation.

Runs the real Master Portfolio backtest with default parameters and writes the
generated report into the ``investment_report`` table (``kind='investment'``)
so the user-facing Reports page surfaces a real backtest report — not the
development sign-offs. Re-uses the worker's real-engine path
(``run_backtest_job``, which imports ``trade``); idempotent via the repo upsert
keyed by ``(strategy_id, as_of_date)``.

Run as ``python -m workbench_api.backtests.canonical`` (manually or on a timer).
Boundary (r): deterministic backtest over read-only data — no execution.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, date, datetime
from types import SimpleNamespace

from sqlalchemy.orm import Session, sessionmaker

from workbench_api.backtests.worker import run_backtest_job
from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.investment_report import InvestmentReportRepository
from workbench_api.db.require_production_db import (
    ScratchDatabaseError,
    require_production_db,
)

logger = logging.getLogger(__name__)

MASTER_STRATEGY_ID = "master_portfolio"
MASTER_TITLE = "Master Portfolio — Quarterly Backtest"


def generate_canonical_reports(session: Session, *, as_of: date | None = None) -> int:
    """Generate + upsert the canonical Master investment report. Returns the
    number of reports written. Raises (so the CLI exits non-zero) when the real
    engine cannot run — e.g. no unified data on the host."""

    report_date = as_of or datetime.now(UTC).date()
    # B050 F001: the worker now dispatches by ``strategy_id`` — set it explicitly
    # on the stand-in so the canonical job keeps running the Master backtest (the
    # worker also defaults a missing strategy_id to master, but be explicit).
    run = SimpleNamespace(
        run_id=f"canonical-{MASTER_STRATEGY_ID}-{report_date.isoformat()}",
        strategy_id=MASTER_STRATEGY_ID,
        params={},
    )
    result = run_backtest_job(run)  # real engine; raises BacktestWorkerError on no data
    InvestmentReportRepository(session).upsert_report(
        strategy_id=MASTER_STRATEGY_ID,
        as_of_date=report_date,
        title=MASTER_TITLE,
        markdown=result["report_markdown"],
        metrics=result["metrics"],
    )
    session.commit()
    return 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.backtests.canonical",
        description="B047 canonical investment report generation (real Master backtest).",
    )
    parser.parse_args(argv)
    # B047-OPS1 F001 — hard-fail before any DB access if WORKBENCH_DB_URL is
    # unset (would silently write the dev scratch DB, not prod — the B047
    # re-verify root cause). Loud non-zero exit, no DB write.
    try:
        require_production_db(entrypoint="canonical")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        count = generate_canonical_reports(session)
    except Exception as exc:  # noqa: BLE001 — surface the failure on the CLI
        logger.exception("canonical_report_generation_failed")
        session.rollback()
        print(f"canonical report generation failed: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()
    print(f"canonical investment reports written: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
