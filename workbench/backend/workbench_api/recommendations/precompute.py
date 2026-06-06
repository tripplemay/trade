"""B044 F002 — Master Portfolio real-scoring precompute.

Imports the ``trade`` package and runs the real Master Portfolio scoring
"as of today" → the final ``{symbol: target_weight}`` plus per-sleeve
breakdown → persists into ``recommendation_snapshot``. The daily
``workbench-recommendations`` timer runs this; the request path reads the DB
(never imports trade — §12.10 AST guard, F003).

Boundary (r-c) (B044): determinstic quant scoring precompute, read-only — it
writes recommendation_snapshot and never touches broker / order-ticket /
execution surfaces.

**Data source honesty (v0.9.21)**: the scoring CODE is real, but the price
DATA is the bundled ETF fixture (``trade/data/fixtures/market_prices.json``,
ships in the wheel) — real market data on the VM is deferred to B045. Every
batch is marked ``master_meta.data_source`` so a fixture run is never passed
off as real. The ``satellite_us_quality`` sleeve needs repo-root CSVs that are
NOT in the wheel; when they're absent (the production VM) it is stubbed to the
defensive asset and marked ``us_quality_status=stubbed_data_unavailable``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any, Protocol

from sqlalchemy.orm import Session

from workbench_api.db.models.recommendation_snapshot import DATA_SOURCE_FIXTURE
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)

logger = logging.getLogger(__name__)


class PrecomputeError(RuntimeError):
    """Master scoring could not produce a target (e.g. no signal date)."""


@dataclass(frozen=True, slots=True)
class MasterTargetResult:
    """Output of the master scoring: aggregated target + attribution + meta."""

    as_of_date: date
    # symbol -> aggregated target weight (unique symbols).
    target_weights: dict[str, float]
    # symbol -> attributed sleeve id (the largest contributor).
    symbol_sleeve: dict[str, str]
    master_meta: dict[str, Any]


class ScoreFn(Protocol):
    def __call__(self) -> MasterTargetResult: ...


@dataclass(frozen=True, slots=True)
class PrecomputeSummary:
    saved: int
    as_of_date: date | None
    data_source: str | None
    error: str | None


_WEIGHT_ROUND_DIGITS = 6


def score_master_target() -> MasterTargetResult:
    """Run the real ``trade`` Master Portfolio scoring on the bundled ETF
    fixture and return the current target. **The only place trade is imported.**

    Resolves each sleeve's child weights via the real
    ``trade.backtest.master_portfolio._resolve_child_weights`` for the latest
    quarter-end signal date (spec §4.3), then aggregates by planning weight
    (the documented Master composition). Resolution is **per-sleeve resilient**:
    a sleeve whose input data is unavailable on the current host (e.g.
    risk_parity needs daily vol history, us_quality needs repo-root CSVs — both
    absent in the bundled fixture / on the wheel-only VM) raises, and that
    sleeve is stubbed to the defensive asset and marked
    ``stubbed_data_unavailable``. Whatever can score (e.g. momentum on the
    monthly fixture) still scores. The price DATA is the bundled fixture →
    ``data_source=fixture`` (real market data is B045)."""

    from trade.backtest.master_portfolio import (  # type: ignore[import-untyped]
        _resolve_child_weights,
        identify_quarter_end_signal_dates,
    )
    from trade.data.loader import load_fixture_prices  # type: ignore[import-untyped]
    from trade.portfolio.master import (  # type: ignore[import-untyped]
        default_master_portfolio_parameters,
    )
    from trade.strategies.global_etf_momentum import (  # type: ignore[import-untyped]
        MomentumParameters,
    )
    from trade.strategies.risk_parity import (  # type: ignore[import-untyped]
        RiskParityParameters,
    )
    from trade.strategies.us_quality_momentum.parameters import (  # type: ignore[import-untyped]
        UsQualityMomentumParameters,
    )

    snapshot = load_fixture_prices()
    records = snapshot.records
    all_dates = tuple(sorted({record.date for record in records}))
    quarter_ends = identify_quarter_end_signal_dates(all_dates)
    if not quarter_ends:
        raise PrecomputeError("no quarter-end signal date available in price records")
    signal_date = quarter_ends[-1]

    params = default_master_portfolio_parameters()
    momentum = MomentumParameters()
    risk_parity = RiskParityParameters()
    us_quality = UsQualityMomentumParameters()

    portfolio_target: dict[str, float] = {}
    symbol_sleeve: dict[str, str] = {}
    symbol_best: dict[str, float] = {}
    planning_weights: dict[str, float] = {}
    sleeve_status: dict[str, str] = {}

    for sleeve in params.sleeves:
        planning_weights[sleeve.sleeve_id] = sleeve.planning_weight
        try:
            child_weights = _resolve_child_weights(
                sleeve,
                records=records,
                signal_date=signal_date,
                defensive_asset=params.defensive_asset,
                momentum_params=momentum,
                risk_parity_params=risk_parity,
                us_quality_params=us_quality,
            )
            sleeve_status[sleeve.sleeve_id] = "scored"
        except Exception as exc:  # noqa: BLE001 — sleeve input data unavailable on host
            logger.warning(
                "recommendations_precompute_sleeve_unavailable",
                extra={"sleeve": sleeve.sleeve_id, "error": str(exc)},
            )
            child_weights = {params.defensive_asset: 1.0}
            sleeve_status[sleeve.sleeve_id] = "stubbed_data_unavailable"

        for symbol, weight in child_weights.items():
            contribution = round(
                sleeve.planning_weight * weight, _WEIGHT_ROUND_DIGITS
            )
            portfolio_target[symbol] = round(
                portfolio_target.get(symbol, 0.0) + contribution, _WEIGHT_ROUND_DIGITS
            )
            if symbol not in symbol_best or contribution > symbol_best[symbol]:
                symbol_best[symbol] = contribution
                symbol_sleeve[symbol] = sleeve.sleeve_id

    master_meta: dict[str, Any] = {
        "data_source": DATA_SOURCE_FIXTURE,
        "planning_weights": planning_weights,
        "sleeve_status": sleeve_status,
        "signal_date": signal_date.isoformat(),
        "fixture_symbols": sorted({record.symbol for record in records}),
        "defensive_asset": params.defensive_asset,
    }
    return MasterTargetResult(
        as_of_date=signal_date,
        target_weights=portfolio_target,
        symbol_sleeve=symbol_sleeve,
        master_meta=master_meta,
    )


def run_precompute(
    session: Session,
    *,
    score_fn: ScoreFn = score_master_target,
    computed_at: datetime | None = None,
) -> PrecomputeSummary:
    """Score the current Master Portfolio target and persist it.

    ``score_fn`` is injectable so tests can supply a fake target without
    importing trade. On a scoring failure the snapshot is left untouched (the
    request path stays graceful on the previous / empty snapshot)."""

    try:
        result = score_fn()
    except Exception as exc:  # noqa: BLE001 — best-effort job; never crash the timer hard
        logger.exception("recommendations_precompute_failed")
        return PrecomputeSummary(saved=0, as_of_date=None, data_source=None, error=str(exc))

    rows: list[dict[str, Any]] = []
    for symbol, weight in result.target_weights.items():
        sleeve = result.symbol_sleeve.get(symbol, "master")
        rows.append(
            {
                "symbol": symbol,
                "sleeve": sleeve,
                "target_weight": weight,
                # Placeholder rationale (rich "why" is B043); honest, not inflated.
                "rationale": (
                    f"{sleeve} sleeve target from the Master Portfolio composition "
                    f"(data_source={result.master_meta.get('data_source')})."
                ),
            }
        )

    repo = RecommendationSnapshotRepository(session)
    saved = repo.save_batch(
        as_of_date=result.as_of_date,
        rows=rows,
        master_meta=result.master_meta,
        computed_at=computed_at or datetime.now(UTC),
    )
    session.commit()
    logger.info(
        "recommendations_precompute_done",
        extra={
            "as_of_date": result.as_of_date.isoformat(),
            "saved": len(saved),
            "data_source": result.master_meta.get("data_source"),
        },
    )
    return PrecomputeSummary(
        saved=len(saved),
        as_of_date=result.as_of_date,
        data_source=result.master_meta.get("data_source"),
        error=None,
    )
