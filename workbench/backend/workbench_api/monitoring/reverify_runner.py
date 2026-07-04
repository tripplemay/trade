"""B080 F003 — reverify runner: data-append → frozen kernel → three landings.

Ties the F003 pieces together for the worker. The three collaborators are injectable
so the orchestration is unit-testable without baostock / ``trade`` (the worker uses
the real defaults; a test passes fakes). Data-append + the frozen backtest are the
long parts — this is why the whole thing runs on the worker, never the request path.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from workbench_api.monitoring.reverify_data_append import append_reverify_snapshot
from workbench_api.monitoring.reverify_kernel import run_frozen_revalidation
from workbench_api.monitoring.reverify_landings import land_results

logger = logging.getLogger(__name__)

AppendFn = Callable[..., dict[str, object]]
KernelFn = Callable[..., dict[str, Any]]
LandFn = Callable[..., dict[str, Any]]


def run_reverify(
    session: Session,
    *,
    strategy_id: str,
    as_of: date,
    repo_root: Path,
    b070_root: Path,
    reverify_root: Path,
    do_append: bool = True,
    append_fn: AppendFn = append_reverify_snapshot,
    kernel_fn: KernelFn = run_frozen_revalidation,
    land_fn: LandFn = land_results,
) -> dict[str, Any]:
    """Run one frozen re-validation end-to-end and return the landing summary.

    ``do_append=False`` skips the baostock fetch and re-validates on whatever data
    already sits at ``reverify_root`` (used when the snapshot was appended out-of-band
    or in a test)."""

    if do_append:
        summary = append_fn(b070_root=b070_root, reverify_root=reverify_root, end=as_of)
        logger.info("reverify data-append: %s", summary)
    payload = kernel_fn(reverify_root, end=as_of)
    result = land_fn(
        session, strategy_id=strategy_id, payload=payload, as_of=as_of, repo_root=repo_root
    )
    logger.info(
        "reverify landed: strategy=%s verdict=%s validated=%s",
        strategy_id, result.get("verdict"), result.get("validated"),
    )
    return result
