"""B057 F001 — ``python -m workbench_api.strategy_modes.cli`` entrypoint.

The monthly ``workbench-regime-precompute`` systemd timer runs this. It scores
the current regime-adaptive target (importing ``trade``) and writes it into the
generic target layer (``recommendation_snapshot`` under ``regime_adaptive``).
Boundary (r-c): read-only quant scoring precompute — it never imports or invokes
any broker / order-ticket / execution surface. The regime mode ships
research-state; producing a target is not a funding decision (B057 §1).
"""

from __future__ import annotations

import argparse
import logging
import sys

from sqlalchemy.orm import sessionmaker

from workbench_api.cli_clock import add_as_of_argument, resolve_now
from workbench_api.db.engine import get_engine
from workbench_api.strategy_modes.regime_precompute import (
    run_regime_precompute,
    score_regime_target,
)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = argparse.ArgumentParser(
        prog="python -m workbench_api.strategy_modes.cli",
        description="B057 monthly regime-adaptive recommendation precompute.",
    )
    add_as_of_argument(parser)
    args = parser.parse_args(argv)

    # B072 F003 — --as-of fast-forwards the regime scoring to a fixed date;
    # omitted → today (UTC), unchanged production run.
    as_of = args.as_of
    score_fn = (lambda: score_regime_target(as_of=as_of)) if as_of else score_regime_target
    computed_at = resolve_now(as_of) if as_of else None

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        summary = run_regime_precompute(
            session, score_fn=score_fn, computed_at=computed_at
        )
    finally:
        session.close()

    print(
        "regime precompute done — "
        f"saved={summary.saved} "
        f"as_of_date={summary.as_of_date} "
        f"data_source={summary.data_source} "
        f"regime={summary.regime} "
        f"error={summary.error}"
    )
    return 0 if summary.error is None and summary.saved > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
