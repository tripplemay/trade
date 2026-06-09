"""B044 F002 — ``python -m workbench_api.recommendations.cli`` entrypoint.

The daily ``workbench-recommendations`` systemd timer runs this. It scores the
current Master Portfolio target (importing ``trade``) and writes
``recommendation_snapshot``. Boundary (r-c): read-only quant scoring precompute
— it never imports or invokes any broker / order-ticket / execution surface.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.recommendations.precompute import run_precompute
from workbench_api.services.explanation import build_default_explainer


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        # B043 F001: build the production LLM explainer (grounded "why"); None on
        # the timer host without the gateway key → deterministic placeholder.
        summary = run_precompute(session, explainer=build_default_explainer())
    finally:
        session.close()

    print(
        "recommendations precompute done — "
        f"saved={summary.saved} "
        f"as_of_date={summary.as_of_date} "
        f"data_source={summary.data_source} "
        f"error={summary.error}"
    )
    return 0 if summary.error is None and summary.saved > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
