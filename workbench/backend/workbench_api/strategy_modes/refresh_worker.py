"""B058 F003 — manual target-refresh job processing (the off-request-path side).

A target-refresh job (``target_refresh_job``) runs a strategy mode's registered
target producer to write a fresh ``recommendation_snapshot`` — generating the
mode's current target on demand instead of waiting for its scheduled timer
(the S1 fix: regime gets a target immediately; Master / future modes reuse it).

Dispatch is by ``strategy_id`` through :data:`_DISPATCH`. Each runner imports
``trade`` LAZILY inside its body, so importing this module is light (no heavy
stack) and the §12.10.2 AST guard scans the ``trade`` imports here — the allowed
off-request-path location. The producers (``recommendations.precompute`` /
``strategy_modes.regime_precompute``) commit their own snapshot; this layer only
records the job's terminal state.

Boundary (r-c): read-only quant scoring precompute — never imports or invokes a
broker / order-ticket / execution surface.

The always-running worker daemon (the B047 backtest worker, extended) calls
:func:`process_next_refresh` each poll; :func:`main` is a standalone one-shot
drain for manual ops (process every queued refresh job, then exit).
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.target_refresh_job import TargetRefreshJobRepository
from workbench_api.db.require_production_db import (
    ScratchDatabaseError,
    require_production_db,
)
from workbench_api.strategy_modes.registry import (
    CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID,
    CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID,
    CN_DIVIDEND_LOWVOL_STRATEGY_ID,
    MASTER_STRATEGY_ID,
    REGIME_STRATEGY_ID,
)

logger = logging.getLogger(__name__)

# Error-kind codes (the frontend i18n maps these to bilingual messages).
ERROR_PRODUCER = "producer_error"
ERROR_EMPTY = "empty_target"
ERROR_INTERRUPTED = "interrupted"
# B058 F003-PROD-1 — the producer reported a data-coverage gap (its price data
# does not cover the strategy universe); actionable: refresh the data.
ERROR_DATA_NOT_COVERED = "data_not_covered"


class RefreshProducerError(RuntimeError):
    """No target producer is wired for the requested strategy_id."""


@dataclass(frozen=True, slots=True)
class ProducerResult:
    """Normalised output of a mode's target producer (whatever its own summary)."""

    saved: int
    as_of_date: str | None
    data_source: str | None
    error: str | None
    # Stable failure code the producer classified (e.g. data_not_covered), or
    # None — the worker forwards it so the frontend shows an actionable message.
    error_kind: str | None = None


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _run_master_producer(session: Session) -> ProducerResult:
    """Master Portfolio target producer (B044) — quant scoring, imports trade."""

    from workbench_api.recommendations.precompute import run_precompute
    from workbench_api.services.explanation import build_default_explainer

    summary = run_precompute(session, explainer=build_default_explainer())
    return ProducerResult(
        saved=summary.saved,
        as_of_date=_iso(summary.as_of_date),
        data_source=summary.data_source,
        error=summary.error,
    )


def _run_regime_producer(session: Session) -> ProducerResult:
    """Regime-adaptive target producer (B057) — quant scoring, imports trade."""

    from workbench_api.strategy_modes.regime_precompute import run_regime_precompute

    summary = run_regime_precompute(session)
    return ProducerResult(
        saved=summary.saved,
        as_of_date=_iso(summary.as_of_date),
        data_source=summary.data_source,
        error=summary.error,
        error_kind=summary.error_kind,
    )


def _run_cn_attack_producer(
    session: Session, strategy_id: str, factor_variant: str
) -> ProducerResult:
    """CN attack advisory producer (B067) — one parameterised body for both modes.

    The quality+momentum and pure-momentum modes share this; ``factor_variant``
    is the only difference. Imports trade lazily (off the request path)."""

    from workbench_api.strategy_modes.cn_attack_precompute import (
        run_cn_attack_precompute,
    )

    summary = run_cn_attack_precompute(
        session, strategy_id, factor_variant=factor_variant
    )
    return ProducerResult(
        saved=summary.saved,
        as_of_date=_iso(summary.as_of_date),
        data_source=summary.data_source,
        error=summary.error,
        error_kind=summary.error_kind,
    )


def _run_cn_attack_quality_momentum_producer(session: Session) -> ProducerResult:
    return _run_cn_attack_producer(
        session, CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID, "quality_momentum"
    )


def _run_cn_attack_pure_momentum_producer(session: Session) -> ProducerResult:
    return _run_cn_attack_producer(
        session, CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID, "pure_momentum"
    )


def _run_cn_dividend_lowvol_producer(session: Session) -> ProducerResult:
    """CN 红利低波 defensive-sleeve producer (B082 F003). Imports trade lazily
    (off the request path) — reads the frozen dividend-lowvol CSVs and publishes the
    current 利差档位 target."""

    from workbench_api.strategy_modes.cn_dividend_lowvol_precompute import (
        run_cn_dividend_lowvol_precompute,
    )

    summary = run_cn_dividend_lowvol_precompute(session, CN_DIVIDEND_LOWVOL_STRATEGY_ID)
    return ProducerResult(
        saved=summary.saved,
        as_of_date=_iso(summary.as_of_date),
        data_source=summary.data_source,
        error=summary.error,
        error_kind=summary.error_kind,
    )


Producer = Callable[[Session], ProducerResult]

# strategy_id → target producer. Adding a mode = append one row here (plus its
# registry entry); the endpoint + worker + dedup are all generic (B058 F003).
_DISPATCH: dict[str, Producer] = {
    MASTER_STRATEGY_ID: _run_master_producer,
    REGIME_STRATEGY_ID: _run_regime_producer,
    CN_ATTACK_QUALITY_MOMENTUM_STRATEGY_ID: _run_cn_attack_quality_momentum_producer,
    CN_ATTACK_PURE_MOMENTUM_STRATEGY_ID: _run_cn_attack_pure_momentum_producer,
    CN_DIVIDEND_LOWVOL_STRATEGY_ID: _run_cn_dividend_lowvol_producer,
}


def run_refresh_job(
    session: Session, strategy_id: str, *, dispatch: dict[str, Producer] | None = None
) -> ProducerResult:
    """Run ``strategy_id``'s target producer (writes recommendation_snapshot).

    ``dispatch`` is injectable so tests supply a fake producer without importing
    ``trade``. Raises :class:`RefreshProducerError` for an unwired strategy."""

    runner = (dispatch or _DISPATCH).get(strategy_id)
    if runner is None:
        raise RefreshProducerError(
            f"no target producer wired for strategy_id={strategy_id!r}"
        )
    return runner(session)


def process_next_refresh(
    session: Session, *, dispatch: dict[str, Producer] | None = None
) -> bool:
    """Claim + process one queued refresh job. Returns ``True`` if one was handled
    (caller skips the idle sleep), ``False`` when the queue was empty.

    Never raises to the caller — a producer failure marks the job ``error`` so the
    worker loop (and the backtest path it shares) keeps running."""

    repo = TargetRefreshJobRepository(session)
    job = repo.claim_next_queued()
    if job is None:
        return False
    # Persist the `running` claim before the (heavy) producer so a crash leaves a
    # visible `running` row, not a lost `queued` one.
    session.commit()
    job_id = job.job_id
    strategy_id = job.strategy_id
    try:
        result = run_refresh_job(session, strategy_id, dispatch=dispatch)
    except Exception as exc:  # noqa: BLE001 — any producer failure → error state
        logger.exception("target_refresh_run_failed", extra={"job_id": job_id})
        session.rollback()
        repo.save_error(
            job_id, f"{type(exc).__name__}: {exc}", error_kind=ERROR_PRODUCER
        )
        session.commit()
        return True

    if result.error is not None:
        repo.save_error(job_id, result.error, error_kind=result.error_kind or ERROR_PRODUCER)
    elif result.saved <= 0:
        repo.save_error(
            job_id,
            "target producer wrote no rows (no usable target)",
            error_kind=ERROR_EMPTY,
        )
    else:
        repo.save_result(
            job_id,
            as_of_date=result.as_of_date,
            saved_count=result.saved,
            data_source=result.data_source,
        )
    session.commit()
    logger.info(
        "target_refresh_done",
        extra={"job_id": job_id, "strategy_id": strategy_id, "saved": result.saved},
    )
    return True


def recover_orphaned_refresh(session: Session) -> int:
    """Reclaim orphaned ``running`` refresh jobs at worker startup → error."""

    reclaimed = TargetRefreshJobRepository(session).recover_orphaned_running(
        error="worker restarted while this refresh was in progress; please re-run",
        error_kind=ERROR_INTERRUPTED,
    )
    session.commit()
    return reclaimed


def main(argv: list[str] | None = None) -> int:  # noqa: ARG001
    """Standalone one-shot drain of the refresh queue (manual ops)."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        require_production_db(entrypoint="refresh-worker")
    except ScratchDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    factory = sessionmaker(bind=get_engine(), autoflush=False, future=True)
    processed = 0
    while True:
        session = factory()
        try:
            handled = process_next_refresh(session)
        finally:
            session.close()
        if not handled:
            break
        processed += 1
    print(f"target-refresh drain done — processed={processed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
