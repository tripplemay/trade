"""B036 F002 — ``python -m workbench_api.advisor.cli`` entrypoint.

Daily advisor precompute, run by the ``workbench-advisor`` systemd timer
(after the market-context fetch so grounding sees fresh market data).
Constructs the real :class:`LLMGateway` (reads ``AIGC_GATEWAY_API_KEY``
from the env file) + a DB session and runs :func:`run_daily`.

Boundary (r) as revised in B036: a scheduler may run CI-safety-gated
advisor precompute. This CLI writes advice to the DB only — it never
imports or invokes any broker / order-ticket / execution surface
(``tests/safety/test_market_scheduler_scope.py`` enforces).
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy.orm import sessionmaker

from workbench_api.advisor.precompute import run_daily
from workbench_api.advisor.service import AdvisorService
from workbench_api.cli_clock import add_as_of_argument
from workbench_api.db.engine import get_engine
from workbench_api.llm.gateway import LLMGateway


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.advisor.cli",
        description="B036 daily advisor precompute.",
    )
    add_as_of_argument(parser)
    args = parser.parse_args(argv)

    advisor = AdvisorService(LLMGateway())
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        # B072 F003 — --as-of pins the advisor run date; omitted → today (UTC).
        summary = run_daily(session, advisor, today=args.as_of)
    finally:
        session.close()
    print(
        f"advisor precompute done — saved={summary.saved} "
        f"skipped={summary.skipped} errors={summary.errors}"
    )
    return 0 if summary.errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
