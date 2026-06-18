"""B067 F002 — ``python -m workbench_api.strategy_modes.cn_attack_cli`` entrypoint.

The two daily ``workbench-cn-attack-*`` systemd timers run this — one per factor
variant. It scores the CN attack mode's current advisory target (importing
``trade`` off the request path) and writes it into the generic target layer
(``recommendation_snapshot`` under the variant's ``strategy_id``).

Usage::

    python -m workbench_api.strategy_modes.cn_attack_cli quality_momentum
    python -m workbench_api.strategy_modes.cn_attack_cli pure_momentum
    python -m workbench_api.strategy_modes.cn_attack_cli            # both (manual ops)

Boundary (r-c): read-only quant scoring precompute — it never imports or invokes
any broker / order-ticket / execution surface. The cn_attack modes ship
research-state and advisory-only; producing a target is not a funding decision
and never auto-trades (B067 §0). ``require_production_db`` (§12.11.1) hard-fails
*before any DB write* if ``WORKBENCH_DB_URL`` is the silent dev-scratch fallback,
so a hand-run never lands the target in the wrong DB.
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
from workbench_api.strategy_modes.cn_attack_precompute import (
    CnAttackPrecomputeSummary,
    run_cn_attack_precompute,
)
from workbench_api.strategy_modes.registry import (
    CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
    CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
)

# factor_variant → strategy_id (the two advisory modes). Selector order matches
# the registry (quality+momentum first).
_VARIANTS: tuple[tuple[str, str], ...] = (
    ("quality_momentum", CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID),
    ("pure_momentum", CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID),
)

Runner = Callable[..., CnAttackPrecomputeSummary]


def _selected(argv: list[str]) -> list[tuple[str, str]]:
    """Resolve the (factor_variant, strategy_id) pairs to run from the args."""

    if not argv:
        return list(_VARIANTS)
    wanted = argv[0]
    matches = [pair for pair in _VARIANTS if pair[0] == wanted]
    if not matches:
        valid = ", ".join(fv for fv, _ in _VARIANTS)
        raise SystemExit(
            f"::error::unknown cn_attack factor variant {wanted!r} — valid: {valid}"
        )
    return matches


def main(argv: list[str] | None = None, *, runner: Runner = run_cn_attack_precompute) -> int:
    """Run the CN attack precompute for the selected variant(s).

    ``runner`` is injectable so tests exercise the dispatch + exit-code logic
    without importing ``trade`` / loading data. Returns non-zero if any variant
    failed or wrote no rows (so the timer surfaces a failed run)."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = list(sys.argv[1:] if argv is None else argv)
    selected = _selected(args)

    # §12.11.1 — hard-fail before any DB write if WORKBENCH_DB_URL is the silent
    # dev-scratch fallback (the precompute writes the production recommendation
    # snapshot; a hand-run must never land it in ./workbench-dev.db).
    try:
        require_production_db(entrypoint="cn-attack-precompute")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    exit_code = 0
    for factor_variant, strategy_id in selected:
        session = factory()
        try:
            summary = runner(session, strategy_id, factor_variant=factor_variant)
        finally:
            session.close()
        print(
            "cn_attack precompute done — "
            f"strategy_id={strategy_id} "
            f"factor_variant={factor_variant} "
            f"saved={summary.saved} "
            f"as_of_date={summary.as_of_date} "
            f"data_source={summary.data_source} "
            f"error={summary.error}"
        )
        if summary.error is not None or summary.saved <= 0:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
