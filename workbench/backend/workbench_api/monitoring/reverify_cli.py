"""B080 F003 — ``python -m workbench_api.monitoring.reverify_cli`` (seasonal enqueue).

The quarterly timer runs this thin, FAST entrypoint: it only enqueues one frozen
re-validation job per monitored strategy (deduped) and commits — the already-running
backtest worker daemon drains them (the long baostock fetch + backtest happens there,
not here). Guards the production DB before the write.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    from workbench_api.db.require_production_db import (
        ScratchDatabaseError,
        require_production_db,
    )

    try:
        require_production_db(entrypoint="reverify")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    from workbench_api.db.engine import get_engine
    from workbench_api.monitoring.reverify_service import (
        REVERIFY_STRATEGIES,
        enqueue_reverify,
    )

    session = sessionmaker(bind=get_engine(), autoflush=False, future=True)()
    try:
        for strategy_id in REVERIFY_STRATEGIES:
            job = enqueue_reverify(session, strategy_id=strategy_id)
            print(f"enqueued reverify {strategy_id}: {job.job_id} ({job.status})")
        session.commit()
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
