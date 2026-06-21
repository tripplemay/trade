"""B044 F002 — ``python -m workbench_api.recommendations.cli`` entrypoint.

The daily ``workbench-recommendations`` systemd timer runs this. It scores the
current Master Portfolio target (importing ``trade``) and writes
``recommendation_snapshot``. Boundary (r-c): read-only quant scoring precompute
— it never imports or invokes any broker / order-ticket / execution surface.
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy.orm import sessionmaker

from workbench_api.cli_clock import add_as_of_argument, resolve_now
from workbench_api.db.engine import get_engine
from workbench_api.recommendations.precompute import run_precompute, score_master_target
from workbench_api.services.explanation import build_default_explainer


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.recommendations.cli",
        description="B044 daily Master Portfolio recommendation precompute.",
    )
    add_as_of_argument(parser)
    args = parser.parse_args(argv)

    # B072 F003 — --as-of fast-forwards the scoring to a fixed date (price-load
    # horizon + snapshot stamp); omitted → today (UTC), unchanged production run.
    as_of = args.as_of
    score_fn = (lambda: score_master_target(as_of=as_of)) if as_of else score_master_target
    computed_at = resolve_now(as_of) if as_of else None

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        # B043 F001: build the production LLM explainer (grounded "why"); None on
        # the timer host without the gateway key → deterministic placeholder.
        summary = run_precompute(
            session,
            score_fn=score_fn,
            computed_at=computed_at,
            explainer=build_default_explainer(),
        )
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
