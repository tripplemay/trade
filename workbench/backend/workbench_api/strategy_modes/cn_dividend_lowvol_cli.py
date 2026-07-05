"""B082 F003 — ``python -m workbench_api.strategy_modes.cn_dividend_lowvol_cli`` entrypoint.

The daily ``workbench-cn-dividend-lowvol`` systemd timer runs this. It scores the
红利低波 defensive-sleeve mode's current advisory target (importing ``trade`` off the
request path) and writes it into the generic target layer (``recommendation_snapshot``
under ``strategy_id=cn_dividend_lowvol``).

Usage::

    python -m workbench_api.strategy_modes.cn_dividend_lowvol_cli

Boundary (r-c): read-only quant scoring precompute — it never imports or invokes any
broker / order-ticket / execution surface. The mode ships research-state and advisory
-only; producing a target is not a funding decision and never auto-trades (spec §3).
``require_production_db`` (§12.11.1) hard-fails *before any DB write* if
``WORKBENCH_DB_URL`` is the silent dev-scratch fallback, so a hand-run never lands the
target in the wrong DB.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.require_production_db import (
    ScratchDatabaseError,
    require_production_db,
)
from workbench_api.strategy_modes.cn_dividend_lowvol_precompute import (
    CnDividendLowvolPrecomputeSummary,
    run_cn_dividend_lowvol_precompute,
)
from workbench_api.strategy_modes.registry import CN_DIVIDEND_LOWVOL_STRATEGY_ID

Runner = Callable[..., CnDividendLowvolPrecomputeSummary]


def main(
    argv: list[str] | None = None,  # noqa: ARG001 — no args; kept for uniform signature
    *,
    runner: Runner = run_cn_dividend_lowvol_precompute,
) -> int:
    """Run the dividend-lowvol precompute.

    ``runner`` is injectable so tests exercise the exit-code logic without importing
    ``trade`` / reading data. Returns non-zero if the run failed or wrote no rows (so the
    timer surfaces a failed run)."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # §12.11.1 — hard-fail before any DB write if WORKBENCH_DB_URL is the silent
    # dev-scratch fallback (the precompute writes the production recommendation
    # snapshot; a hand-run must never land it in ./workbench-dev.db).
    try:
        require_production_db(entrypoint="cn-dividend-lowvol-precompute")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    session = factory()
    try:
        summary = runner(session, CN_DIVIDEND_LOWVOL_STRATEGY_ID)
    finally:
        session.close()
    print(
        "cn_dividend_lowvol precompute done — "
        f"strategy_id={CN_DIVIDEND_LOWVOL_STRATEGY_ID} "
        f"saved={summary.saved} "
        f"as_of_date={summary.as_of_date} "
        f"data_source={summary.data_source} "
        f"error={summary.error}"
    )
    return 0 if summary.error is None and summary.saved > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
