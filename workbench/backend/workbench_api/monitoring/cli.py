"""B080 F002 — ``python -m workbench_api.monitoring.cli`` (weekly monitoring job).

Thin entrypoint: guard the production DB, resolve the two optional CSV inputs
(cn_csi300 benchmark + cn_size PIT caps, best-effort under WORKBENCH_DATA_ROOT),
run the metrics orchestration, commit. Read-only / advisory-only — writes only the
``monitoring_metric`` table; never imports a broker SDK or execution code (the
systemd unit + tests/safety/test_market_scheduler_scope.py enforce this).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def _first_existing(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.is_file():
            return path
    return None


def _resolve_inputs() -> tuple[Path | None, Path | None]:
    """Best-effort locate cn_csi300.csv + cn_size.csv (None → the dependent metric
    degrades honestly instead of failing)."""

    data_root = os.environ.get("WORKBENCH_DATA_ROOT")
    # repo root from .../workbench_api/monitoring/cli.py — local layout only.
    repo_guess = Path(__file__).resolve().parents[4]
    roots = [Path(data_root)] if data_root else []
    csi300 = _first_existing(
        *[r / "snapshots" / "benchmark" / "cn_csi300.csv" for r in roots],
        repo_guess / "data" / "snapshots" / "benchmark" / "cn_csi300.csv",
    )
    size = _first_existing(
        *[r / "research" / "b076" / "cn_size.csv" for r in roots],
        repo_guess / "data" / "research" / "b076" / "cn_size.csv",
    )
    return csi300, size


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(prog="workbench-monitoring")
    parser.add_argument(
        "--as-of", type=date.fromisoformat, default=None,
        help="Monitoring date (default: today UTC).",
    )
    args = parser.parse_args(argv)
    as_of = args.as_of or datetime.now(UTC).date()

    # §12.11.1 — hard-fail BEFORE any DB write if pointed at the dev scratch DB.
    from workbench_api.db.require_production_db import (
        ScratchDatabaseError,
        require_production_db,
    )

    try:
        require_production_db(entrypoint="monitoring")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    from workbench_api.db.engine import get_engine
    from workbench_api.monitoring.metrics_job import run_monitoring

    csi300_path, size_path = _resolve_inputs()
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        written = run_monitoring(
            session, as_of=as_of, cn_csi300_path=csi300_path, cn_size_path=size_path
        )
        session.commit()
    finally:
        session.close()
    print(
        f"monitoring metrics — as_of={as_of.isoformat()} written={written} "
        f"csi300={'yes' if csi300_path else 'no'} cn_size={'yes' if size_path else 'no'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
