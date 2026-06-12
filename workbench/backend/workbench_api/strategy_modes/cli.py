"""B057 F001 — ``python -m workbench_api.strategy_modes.cli`` entrypoint.

The monthly ``workbench-regime-precompute`` systemd timer runs this. It scores
the current regime-adaptive target (importing ``trade``) and writes it into the
generic target layer (``recommendation_snapshot`` under ``regime_adaptive``).
Boundary (r-c): read-only quant scoring precompute — it never imports or invokes
any broker / order-ticket / execution surface. The regime mode ships
research-state; producing a target is not a funding decision (B057 §1).
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.strategy_modes.regime_precompute import run_regime_precompute


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        summary = run_regime_precompute(session)
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
