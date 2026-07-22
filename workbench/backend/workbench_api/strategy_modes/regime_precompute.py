"""B057 F001 — regime-adaptive target precompute (the regime mode's producer).

Imports the ``trade`` package and runs the **existing, unchanged** regime engine
(``run_regime_adaptive_monthly_backtest``) over a trailing window of monthly
signal dates, then publishes the *final period's* effective weights as the
regime mode's current target into the generic target layer
(``recommendation_snapshot`` keyed by ``strategy_id="regime_adaptive"``). The
monthly ``workbench-regime-precompute`` timer runs this; the request path reads
the DB (never imports trade — §12.10 AST guard).

Why a trailing window, not a single date: the regime detector derives the
current regime (NORMAL / BEAR / CRISIS) from the *prior* period's portfolio
volatility, so a one-shot run would always see an empty prior and report NORMAL.
Running the engine over a window means the final period's regime is grounded in
the real evolving portfolio — we then take that final allocation as "today's
target". This reuses the tested engine verbatim; the precompute never changes
the regime algorithm (B057 hard boundary: research-state, no prediction).

Boundary (r-c) (B057): deterministic quant target precompute, read-only — it
writes ``recommendation_snapshot`` and never touches broker / order-ticket /
execution surfaces. The regime mode ships research-state (``funding_state``
``research``); producing a target gives the *capability* to surface/paper/
(F004) trade it, never the funding decision.

**Data source honesty:** the engine CODE is always real. The price DATA is real
when the VM ``WORKBENCH_DATA_ROOT`` unified prices cover the regime universe
(B045 F001 refresh; B057 F001 added the 5 missing regime ETFs to the refresh
universe), else the bundled fixture. ``meta.data_source`` is marked ``real`` /
``mixed`` (some regime assets missing real prices) / ``fixture`` honestly.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy.orm import Session

from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.strategy_modes.registry import REGIME_STRATEGY_ID

if TYPE_CHECKING:
    from trade.data.loader import PriceBar  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_PRICES_SOURCE_REAL = "real"
_PRICES_SOURCE_MIXED = "mixed"
_PRICES_SOURCE_FIXTURE = "fixture"
_WEIGHT_ROUND_DIGITS = 6
# Drop target weights below this from the published snapshot (regime routes
# residual to the defensive asset, so most universe symbols sit at exactly 0.0).
_MIN_WEIGHT = 1e-6


# Error-kind codes the refresh worker / frontend map to a friendly message.
# B058 F003-PROD-1: distinguish "the price data does not cover the regime
# universe" (actionable: refresh the data) from an unexpected scoring bug.
ERROR_KIND_DATA_NOT_COVERED = "data_not_covered"
ERROR_KIND_SCORING = "scoring_error"

# The crisis label the regime detector emits (mirrors
# trade.strategies.regime_adaptive.regime.REGIME_CRISIS without a top-level trade
# import — this module imports trade lazily inside the scoring functions).
_REGIME_CRISIS = "CRISIS"


class RegimePrecomputeError(RuntimeError):
    """Regime scoring could not produce a target (e.g. insufficient history).

    Raised when the available price data cannot drive the (unchanged, tested)
    regime engine to a target — almost always a data-coverage gap rather than an
    algorithm fault, so the refresh worker maps it to ``data_not_covered``."""


@dataclass(frozen=True, slots=True)
class RegimeTargetResult:
    """Output of the regime scoring: current target + attribution + meta."""

    as_of_date: date
    # symbol -> target weight (non-zero only, sums to ~1.0).
    target_weights: dict[str, float]
    # symbol -> regime asset category (used as the snapshot ``sleeve`` column).
    symbol_sleeve: dict[str, str]
    meta: dict[str, Any]


class RegimeScoreFn(Protocol):
    def __call__(self) -> RegimeTargetResult: ...


@dataclass(frozen=True, slots=True)
class RegimePrecomputeSummary:
    saved: int
    as_of_date: date | None
    data_source: str | None
    regime: str | None
    error: str | None
    # B058 F003-PROD-1 — stable code for the failure class (data_not_covered /
    # scoring_error), None on success. The refresh worker forwards it so the
    # frontend shows an actionable message instead of a vague "producer error".
    error_kind: str | None = None


def score_regime_target(*, as_of: date | None = None) -> RegimeTargetResult:
    """Load the regime universe prices and compute the current regime target.

    **The only place trade is imported for production scoring.** Prices come
    from :func:`_load_regime_records` (real unified daily prices on the VM, else
    the bundled fixture). Delegates the pipeline to :func:`compute_regime_target`
    so the engine logic is unit-testable against synthetic records without disk.

    ``as_of`` (B072 F003) pins the price-load horizon to a fixed date instead of
    today (UTC) so a CI fast-forward runs the monthly timer "as of" that date.
    ``None`` (the default) keeps the production wall-clock behaviour unchanged.
    """

    from trade.strategies.regime_adaptive.config import (  # type: ignore[import-untyped]
        default_regime_adaptive_config,
    )

    config = default_regime_adaptive_config()
    universe = tuple(entry.symbol for entry in config.universe)
    records, prices_source = _load_regime_records(universe, as_of=as_of)
    return compute_regime_target(records, prices_source=prices_source, config=config)


def compute_regime_target(
    records: tuple[PriceBar, ...],
    *,
    prices_source: str = _PRICES_SOURCE_FIXTURE,
    config: Any | None = None,
) -> RegimeTargetResult:
    """Run the regime engine over ``records`` → the current published target.

    Pure over its inputs (imports the trade engine lazily) so it is exercisable
    with synthetic records in unit tests. Builds a trailing window of monthly
    signal dates, runs the unchanged ``run_regime_adaptive_monthly_backtest``,
    and takes the **final period's** effective weights as today's target.
    """

    from trade.strategies.regime_adaptive.backtest import (  # type: ignore[import-untyped]
        run_regime_adaptive_monthly_backtest,
    )
    from trade.strategies.regime_adaptive.config import (
        default_regime_adaptive_config,
    )

    if config is None:
        config = default_regime_adaptive_config()
    category_by_symbol = {entry.symbol: entry.category for entry in config.universe}

    # B058 F003-PROD-1 — name the regime symbols the price data does NOT cover, so
    # every "could not build a target" failure is actionable ("run data-refresh")
    # instead of a vague scoring error. The unified prices file missing the regime
    # ETFs (DBC/IEF/QQQ/TLT/VWO) — the engine then raises "missing price history
    # for required asset QQQ" — is the prod root cause.
    universe = tuple(entry.symbol for entry in config.universe)
    covered = {record.symbol.upper() for record in records}
    missing = [sym for sym in universe if sym.upper() not in covered]
    coverage_hint = (
        f" — regime price coverage incomplete: {len(covered)}/{len(universe)} "
        f"universe symbols present, missing {missing}. Run the data-refresh job "
        f"to populate the unified prices file."
        if missing
        else ""
    )

    if not records:
        raise RegimePrecomputeError(
            f"no price records available for the regime universe{coverage_hint}"
        )

    all_dates = tuple(sorted({record.date for record in records}))
    last_date = all_dates[-1]
    # Each signal date needs a trading date AFTER it (T+1 open execution), so a
    # month-end that is the latest observed date (the current, incomplete month)
    # is excluded — the current published target is the last COMPLETE monthly
    # rebalance, valued through to the latest date.
    signal_dates = tuple(d for d in _monthly_signal_dates(all_dates) if d < last_date)
    if len(signal_dates) < 2:
        raise RegimePrecomputeError(
            "need >= 2 monthly signal dates for regime detection "
            f"(got {len(signal_dates)} from {len(all_dates)} trading dates){coverage_hint}"
        )

    try:
        result = run_regime_adaptive_monthly_backtest(records, signal_dates, config=config)
    except RegimePrecomputeError:
        raise
    except Exception as exc:  # noqa: BLE001 — reclassify a coverage-driven engine fault
        # The engine rejected the (incomplete) universe, e.g. "missing price
        # history for required asset QQQ". When the data does not cover the
        # universe this is a data gap (actionable); with full coverage it is a
        # genuine engine fault, so re-raise unchanged (→ scoring_error).
        if missing:
            raise RegimePrecomputeError(
                f"regime engine could not run ({exc}){coverage_hint}"
            ) from exc
        raise
    if not result.rebalance_results:
        raise RegimePrecomputeError(
            f"regime backtest produced no rebalance periods{coverage_hint}"
        )

    final = result.rebalance_results[-1]
    target_weights = _finalize_weights(final.effective_weights, config.defensive_symbol)
    if not target_weights:
        raise RegimePrecomputeError(
            f"regime target is empty after finalisation{coverage_hint}"
        )

    symbol_sleeve = {
        symbol: category_by_symbol.get(symbol, "regime") for symbol in target_weights
    }

    # B111 F003 (P0-3) — daily crisis RE-EVALUATION on the LATEST (possibly
    # partial-month) data, using the current target as the held book. The
    # published rebalance target above is still the last COMPLETE month
    # (调仓仍月度); this evaluation NEVER advances it — it only surfaces a crisis
    # forming mid-month via meta + a WARNING, so a daily timer catches it instead
    # of the strategy going 7 weeks without looking at the market (评估≠交易).
    current_state = evaluate_current_regime(records, target_weights, config, as_of=last_date)
    if current_state.regime == _REGIME_CRISIS:
        logger.warning(
            "regime_current_crisis_detected",
            extra={
                "as_of": last_date.isoformat(),
                "fast_slow_ratio": current_state.fast_slow_ratio,
                "spy_trend_signal": current_state.spy_trend_signal,
            },
        )

    meta: dict[str, Any] = {
        "data_source": prices_source,
        "prices_source": prices_source,
        "signal_date": final.signal_date.isoformat(),
        "regime": final.regime_state.regime,
        "current_regime": current_state.regime,
        "current_regime_as_of": last_date.isoformat(),
        "cadence": "monthly",
        "universe_symbols": sorted(category_by_symbol),
        "defensive_asset": config.defensive_symbol,
        "l1_active": final.l1_active,
        "passing_symbols": list(final.sleeve_allocation.passing_symbols),
        "gated_symbols": list(final.sleeve_allocation.gated_symbols),
    }
    return RegimeTargetResult(
        as_of_date=final.signal_date,
        target_weights=target_weights,
        symbol_sleeve=symbol_sleeve,
        meta=meta,
    )


def evaluate_current_regime(
    records: tuple[PriceBar, ...],
    prior_weights: dict[str, float],
    config: Any,
    *,
    as_of: date | None = None,
) -> Any:
    """Detect the CURRENT regime from the latest data — a read-only crisis check.

    B111 F003 (P0-3): the regime detector classifies NORMAL / BEAR / CRISIS from
    the *held* portfolio's fast/slow volatility + the SPY 200-day trend as of the
    latest observed date (including the current, incomplete month). This is the
    "evaluate daily" half of "evaluate ≠ trade": it reuses the unchanged, tested
    ``detect_regime`` and never rebalances — the caller keeps the monthly target.
    Returns the engine's ``RegimeState``."""

    from trade.strategies.regime_adaptive.regime import (  # type: ignore[import-untyped]
        detect_regime,
    )

    if not records:
        raise RegimePrecomputeError("no price records for current-regime evaluation")
    latest = as_of or max(record.date for record in records)
    return detect_regime(records, prior_weights, config, latest)


def run_regime_precompute(
    session: Session,
    *,
    score_fn: RegimeScoreFn = score_regime_target,
    computed_at: datetime | None = None,
) -> RegimePrecomputeSummary:
    """Score the current regime target and persist it into the target layer.

    ``score_fn`` is injectable so tests can supply a fake target without
    importing trade / loading prices. Best-effort: on a scoring failure the
    snapshot is left untouched (the request path stays graceful on the previous
    target). Persists under ``strategy_id="regime_adaptive"`` so it never
    tramples Master's rows (the repo delete is scoped by strategy_id).
    """

    try:
        result = score_fn()
    except RegimePrecomputeError as exc:
        # A data-coverage / insufficient-history failure (the engine is unchanged
        # and tested) — actionable: refresh the price data (B058 F003-PROD-1).
        logger.warning("regime_precompute_data_not_covered: %s", exc)
        return RegimePrecomputeSummary(
            saved=0, as_of_date=None, data_source=None, regime=None,
            error=str(exc), error_kind=ERROR_KIND_DATA_NOT_COVERED,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort job; never crash the timer
        logger.exception("regime_precompute_failed")
        return RegimePrecomputeSummary(
            saved=0, as_of_date=None, data_source=None, regime=None,
            error=str(exc), error_kind=ERROR_KIND_SCORING,
        )

    data_source = result.meta.get("data_source")
    regime = result.meta.get("regime")
    rows: list[dict[str, Any]] = []
    for symbol, weight in result.target_weights.items():
        sleeve = result.symbol_sleeve.get(symbol, "regime")
        rows.append(
            {
                "symbol": symbol,
                "sleeve": sleeve,
                "target_weight": weight,
                "rationale": _regime_rationale(symbol, sleeve, regime),
            }
        )

    repo = RecommendationSnapshotRepository(session)
    saved = repo.save_batch(
        strategy_id=REGIME_STRATEGY_ID,
        as_of_date=result.as_of_date,
        rows=rows,
        master_meta=result.meta,
        computed_at=computed_at or datetime.now(UTC),
    )
    session.commit()
    logger.info(
        "regime_precompute_done",
        extra={
            "as_of_date": result.as_of_date.isoformat(),
            "saved": len(saved),
            "data_source": data_source,
            "regime": regime,
        },
    )
    return RegimePrecomputeSummary(
        saved=len(saved),
        as_of_date=result.as_of_date,
        data_source=data_source,
        regime=regime,
        error=None,
    )


def _load_regime_records(
    universe: tuple[str, ...], *, as_of: date | None = None
) -> tuple[tuple[PriceBar, ...], str]:
    """Return ``(records, prices_source)`` for the regime universe.

    Mirrors the Master precompute loader (B045 F002): trust the VM unified daily
    prices as REAL only when the data-root override is set AND the unified file
    exists; classify ``real`` (all 9 regime assets present) vs ``mixed`` (some
    missing) honestly. Local / CI (no override) fall back to the bundled fixture.

    ``as_of`` (B072 F003) is the price-load upper bound; ``None`` → today (UTC),
    unchanged production behaviour.
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

    if data_root_override() is not None and unified_prices_path(UNIFIED_PRICES_PATH).exists():
        by_ticker = load_prices(list(universe), as_of or datetime.now(UTC).date())
        records = tuple(bar for bars in by_ticker.values() for bar in bars)
        if records:
            present = sum(1 for symbol in universe if by_ticker.get(symbol))
            source = (
                _PRICES_SOURCE_REAL if present == len(universe) else _PRICES_SOURCE_MIXED
            )
            return records, source
        logger.warning(
            "regime_precompute_real_prices_empty",
            extra={"reason": "unified prices file present but yielded no rows; using fixture"},
        )

    universe_set = set(universe)
    snapshot = load_fixture_prices()
    fixture_records = tuple(
        record for record in snapshot.records if record.symbol in universe_set
    )
    return fixture_records, _PRICES_SOURCE_FIXTURE


def _monthly_signal_dates(all_dates: tuple[date, ...]) -> tuple[date, ...]:
    """Last trading date observed in each calendar month (ascending).

    The regime engine applies its rebalance cadence via the caller's signal
    dates (config carries no cadence — B019 note). The regime *mode* re-evaluates
    monthly (B057), so we hand the engine one signal date per month. This selects
    signal dates only; it does not touch the regime algorithm.
    """

    last_by_month: dict[tuple[int, int], date] = {}
    for trading_date in all_dates:
        key = (trading_date.year, trading_date.month)
        existing = last_by_month.get(key)
        if existing is None or trading_date > existing:
            last_by_month[key] = trading_date
    return tuple(last_by_month[key] for key in sorted(last_by_month))


def _finalize_weights(
    weights: dict[str, float], defensive_symbol: str
) -> dict[str, float]:
    """Drop near-zero weights, round, and renormalise to sum 1.0.

    Regime ``effective_weights`` span the full universe with most entries at
    0.0; the published snapshot keeps only the held positions. The residual from
    rounding/dropping is routed to the defensive asset so the set sums to 1.0
    (the repo's save_batch guard refuses a set that does not sum to 1.0 ±1e-3).
    """

    kept = {
        symbol.upper(): round(float(weight), _WEIGHT_ROUND_DIGITS)
        for symbol, weight in weights.items()
        if float(weight) > _MIN_WEIGHT
    }
    if not kept:
        return {}
    total = sum(kept.values())
    if total <= 0:
        return {}
    normalised = {
        symbol: round(weight / total, _WEIGHT_ROUND_DIGITS)
        for symbol, weight in kept.items()
    }
    residual = round(1.0 - sum(normalised.values()), _WEIGHT_ROUND_DIGITS)
    if abs(residual) > 0:
        anchor = defensive_symbol.upper()
        if anchor not in normalised:
            anchor = max(normalised, key=lambda sym: normalised[sym])
        normalised[anchor] = round(
            normalised[anchor] + residual, _WEIGHT_ROUND_DIGITS
        )
    return normalised


def _regime_rationale(symbol: str, sleeve: str, regime: str | None) -> str:
    """Deterministic Chinese rationale for a regime target row (research-state).

    Grounded in the asset's category + the detected regime — no LLM, no return
    prediction (B057 research-state boundary). The surfaces mark the whole mode
    研究态; this line is the per-position "why it is held".
    """

    regime_label = {
        "NORMAL": "正常",
        "BEAR": "熊市",
        "CRISIS": "危机",
    }.get(regime or "", regime or "未知")
    category_label = {
        "risk_core": "风险核心",
        "stabilizer": "稳定器",
        "defensive": "防御",
    }.get(sleeve, sleeve)
    return (
        f"{symbol}（{category_label}）：当前市场状态判定为「{regime_label}」，"
        "由智能择时研究组合自适应配置；研究态，前向验证中，非收益预测。"
    )
