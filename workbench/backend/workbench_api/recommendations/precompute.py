"""B044 F002 — Master Portfolio real-scoring precompute.

Imports the ``trade`` package and runs the real Master Portfolio scoring
"as of today" → the final ``{symbol: target_weight}`` plus per-sleeve
breakdown → persists into ``recommendation_snapshot``. The daily
``workbench-recommendations`` timer runs this; the request path reads the DB
(never imports trade — §12.10 AST guard, F003).

Boundary (r-c) (B044): determinstic quant scoring precompute, read-only — it
writes recommendation_snapshot and never touches broker / order-ticket /
execution surfaces.

**Data source honesty (v0.9.21, B045 F003)**: the scoring CODE is always real.
The price DATA is now **granular** — when the VM ``WORKBENCH_DATA_ROOT`` is set
(B045 F002), the precompute reads the real unified daily prices the B045 F001
refresh job wrote and feeds them into the scoring ``records``, so risk_parity
gets daily vol history and the us_quality equities appear on the signal date.
Local / CI / a pre-refresh VM (env unset, or no unified file) fall back to the
bundled monthly ETF fixture (``trade/data/fixtures/market_prices.json``).

``master_meta.data_source`` is marked honestly per run:

* ``real`` — real prices read AND every implemented sleeve scored.
* ``mixed`` — real prices read but ≥1 implemented sleeve still stubbed to the
  defensive asset (its input data was unavailable on the host).
* ``fixture`` — the bundled fixture drove the scoring (no real prices).

Per-sleeve ``sleeve_status`` + ``prices_source`` carry the detail so a partial
run is never passed off as full real.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy.orm import Session

from workbench_api.data_refresh.refresh import price_universe
from workbench_api.db.models.recommendation_snapshot import (
    DATA_SOURCE_FIXTURE,
    DATA_SOURCE_MIXED,
    DATA_SOURCE_REAL,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.recommendations.rationale import generate_rationale
from workbench_api.services.explanation import ExplanationService

if TYPE_CHECKING:
    from trade.data.loader import PriceBar  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_SLEEVE_STATUS_STUBBED = "stubbed_data_unavailable"
_SLEEVE_STATUS_SCORED = "scored"
_PRICES_SOURCE_REAL = "real"
_PRICES_SOURCE_FIXTURE = "fixture"


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
    """Run the real ``trade`` Master Portfolio scoring and return the current
    target. **The only place trade is imported.**

    Prices come from :func:`_load_scoring_records` — real unified daily prices
    (B045 F001 refresh, read via the F002 ``WORKBENCH_DATA_ROOT`` loader) on the
    VM, else the bundled monthly ETF fixture. Resolves each sleeve's child
    weights via the real ``trade.backtest.master_portfolio._resolve_child_weights``
    for the latest quarter-end signal date (spec §4.3), then aggregates by
    planning weight (the documented Master composition). Resolution is
    **per-sleeve resilient**: a sleeve whose input data is unavailable on the
    current host (e.g. risk_parity needs daily vol history, us_quality needs
    fundamentals — both absent in the bundled fixture) raises, and that sleeve is
    stubbed to the defensive asset and marked ``stubbed_data_unavailable``.
    Whatever can score still scores. ``master_meta.data_source`` is then marked
    ``real`` / ``mixed`` / ``fixture`` per :func:`_classify_data_source`."""

    from trade.backtest.master_portfolio import (  # type: ignore[import-untyped]
        _resolve_child_weights,
        identify_quarter_end_signal_dates,
    )
    from trade.portfolio.master import (  # type: ignore[import-untyped]
        default_master_portfolio_parameters,
    )
    from trade.strategies.global_etf_momentum import (  # type: ignore[import-untyped]
        MomentumParameters,
    )
    from trade.strategies.hk_china_momentum.parameters import (  # type: ignore[import-untyped]
        HkChinaMomentumParameters,
    )
    from trade.strategies.risk_parity import (  # type: ignore[import-untyped]
        RiskParityParameters,
    )
    from trade.strategies.us_quality_momentum.parameters import (  # type: ignore[import-untyped]
        UsQualityMomentumParameters,
    )

    records, prices_source = _load_scoring_records()
    all_dates = tuple(sorted({record.date for record in records}))
    quarter_ends = identify_quarter_end_signal_dates(all_dates)
    if not quarter_ends:
        raise PrecomputeError("no quarter-end signal date available in price records")
    signal_date = quarter_ends[-1]

    params = default_master_portfolio_parameters()
    momentum = MomentumParameters()
    risk_parity = RiskParityParameters()
    us_quality = UsQualityMomentumParameters()
    hk_china = HkChinaMomentumParameters()

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
                hk_china_params=hk_china,
            )
            sleeve_status[sleeve.sleeve_id] = _SLEEVE_STATUS_SCORED
        except Exception as exc:  # noqa: BLE001 — sleeve input data unavailable on host
            logger.warning(
                "recommendations_precompute_sleeve_unavailable",
                extra={"sleeve": sleeve.sleeve_id, "error": str(exc)},
            )
            child_weights = {params.defensive_asset: 1.0}
            sleeve_status[sleeve.sleeve_id] = _SLEEVE_STATUS_STUBBED

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

    data_source = _classify_data_source(prices_source, sleeve_status)
    master_meta: dict[str, Any] = {
        "data_source": data_source,
        "prices_source": prices_source,
        "planning_weights": planning_weights,
        "sleeve_status": sleeve_status,
        "signal_date": signal_date.isoformat(),
        "record_symbols": sorted({record.symbol for record in records}),
        "defensive_asset": params.defensive_asset,
    }
    return MasterTargetResult(
        as_of_date=signal_date,
        target_weights=portfolio_target,
        symbol_sleeve=symbol_sleeve,
        master_meta=master_meta,
    )


def _load_scoring_records() -> tuple[tuple[PriceBar, ...], str]:
    """Return ``(records, prices_source)`` for the Master scoring.

    Prefers the **real** unified daily prices the B045 F001 refresh job wrote
    (read via the B045 F002 ``WORKBENCH_DATA_ROOT``-aware loader) so risk_parity
    has daily vol history and the us_quality equities appear on the signal date.
    Falls back to the bundled monthly ETF fixture when the VM data root is unset
    (local / CI) or the unified file is absent / empty (pre-refresh VM) — the
    real-data path is opt-in and never breaks the deterministic fixture run.
    """

    from trade.data.data_root import (  # type: ignore[import-untyped]
        data_root_override,
        unified_prices_path,
    )
    from trade.data.loader import (
        UNIFIED_PRICES_PATH,
        load_fixture_prices,
        load_prices,
    )

    # Only trust the VM path as REAL when the unified file the F001 refresh job
    # writes actually exists. Without this guard, an env-set-but-pre-refresh VM
    # would have ``load_prices`` silently fall back to the bundled B025 fixture
    # (loader's 2nd tier) and we'd mislabel that fixture data as ``real``.
    if data_root_override() is not None and unified_prices_path(UNIFIED_PRICES_PATH).exists():
        by_ticker = load_prices(list(price_universe()), date.today())
        records = tuple(bar for bars in by_ticker.values() for bar in bars)
        if records:
            return records, _PRICES_SOURCE_REAL
        logger.warning(
            "recommendations_precompute_real_prices_empty",
            extra={"reason": "unified prices file present but yielded no rows; using fixture"},
        )

    snapshot = load_fixture_prices()
    return snapshot.records, _PRICES_SOURCE_FIXTURE


def _classify_data_source(prices_source: str, sleeve_status: dict[str, str]) -> str:
    """Honest top-level provenance from the price source + per-sleeve outcome.

    * fixture prices → ``fixture`` (everything fixture-derived).
    * real prices, every implemented sleeve scored → ``real``.
    * real prices, ≥1 sleeve stubbed (its data was unavailable) → ``mixed``.
    """

    if prices_source != _PRICES_SOURCE_REAL:
        return DATA_SOURCE_FIXTURE
    if any(status == _SLEEVE_STATUS_STUBBED for status in sleeve_status.values()):
        return DATA_SOURCE_MIXED
    return DATA_SOURCE_REAL


def run_precompute(
    session: Session,
    *,
    score_fn: ScoreFn = score_master_target,
    computed_at: datetime | None = None,
    explainer: ExplanationService | None = None,
) -> PrecomputeSummary:
    """Score the current Master Portfolio target and persist it.

    ``score_fn`` is injectable so tests can supply a fake target without
    importing trade. On a scoring failure the snapshot is left untouched (the
    request path stays graceful on the previous / empty snapshot).

    B043 F001: each row's ``rationale`` is a grounded LLM "why" (via
    ``explainer``; the CLI builds the production one with
    :func:`build_default_explainer`, tests inject a stub or leave it ``None``).
    Idempotent — when a snapshot for the computed ``as_of_date`` already exists
    (the signal date only changes quarterly, but the timer runs daily) the
    existing per-symbol rationale is reused, so the LLM is not re-billed for an
    unchanged target. ``explainer is None`` (default) → deterministic
    placeholder, so unit tests never touch the network."""

    try:
        result = score_fn()
    except Exception as exc:  # noqa: BLE001 — best-effort job; never crash the timer hard
        logger.exception("recommendations_precompute_failed")
        return PrecomputeSummary(saved=0, as_of_date=None, data_source=None, error=str(exc))

    repo = RecommendationSnapshotRepository(session)

    # Idempotent reuse: if the latest snapshot is already for this as_of_date,
    # reuse its rationales (no LLM re-call for an unchanged target).
    existing = repo.latest_snapshot()
    existing_rationale: dict[str, str] = {
        row.symbol: row.rationale
        for row in existing
        if row.as_of_date == result.as_of_date and row.rationale
    }
    # Reuse path: existing rationales for this as_of_date → no LLM re-call.
    active_explainer = None if existing_rationale else explainer

    data_source = result.master_meta.get("data_source")
    planning_weights = result.master_meta.get("planning_weights") or {}
    sleeve_status = result.master_meta.get("sleeve_status") or {}
    signal_date = result.master_meta.get("signal_date")

    rows: list[dict[str, Any]] = []
    for symbol, weight in result.target_weights.items():
        sleeve = result.symbol_sleeve.get(symbol, "master")
        if symbol in existing_rationale:
            rationale = existing_rationale[symbol]
        else:
            rationale = generate_rationale(
                active_explainer,
                symbol=symbol,
                sleeve=sleeve,
                target_weight=weight,
                planning_weight=planning_weights.get(sleeve),
                sleeve_status=sleeve_status.get(sleeve),
                data_source=data_source,
                signal_date=signal_date,
            )
        rows.append(
            {
                "symbol": symbol,
                "sleeve": sleeve,
                "target_weight": weight,
                "rationale": rationale,
            }
        )

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
