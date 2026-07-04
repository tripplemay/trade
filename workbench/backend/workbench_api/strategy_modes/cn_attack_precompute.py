"""B067 F001 — CN attack advisory target precompute (the producer for both modes).

Imports the ``trade`` package and runs the **existing, unchanged** CN attack
daily-monitor / no-trade-band engine via
:func:`trade.backtest.cn_attack_momentum_quality.live.compute_cn_attack_live_target`,
then publishes the band-managed current target into the generic target layer
(``recommendation_snapshot`` keyed by ``strategy_id``). The daily
``workbench-cn-attack-*`` timers (F002) run this; the request path reads the DB
(never imports trade — §12.10.2 AST guard).

One parameterised producer serves both modes — quality+momentum and pure momentum
differ only by ``factor_variant``. The two strategy ids are independent join keys,
so each variant gets its own recommendation stream / account.

Three things this layer must get right (spec §3):

1. **cash-buffer → 1.0 (the head trap).** The CN portfolio holds a cash buffer
   (``CnPortfolioWeights.cash_buffer``), so the invested weights do NOT sum to 1.0;
   ``save_batch`` refuses a set that misses 1.0 (±1e-3). We append an explicit
   ``CASH`` row = ``1 − sum(invested)`` so the persisted target is fully allocated.
2. **获利了结 (profit-take) landed.** The live target's ``profit_take`` (names
   rotated out of the top-N today) and the rebalance flag are written into the
   snapshot meta + per-row rationale, so the position-diff "卖到零" list shows
   *why* a name leaves (跌出 top-N / 调仓).
3. **★OOS honesty (spec §0, non-negotiable).** Every snapshot's ``master_meta``
   carries the cn_attack-specific unvalidated / negative-OOS caveat so the surface
   marks it honestly — never an implication that this is a validated, funded edge.

Boundary (r-c): deterministic quant target precompute, read-only — it writes
``recommendation_snapshot`` and never touches broker / order-ticket / execution
surfaces. The modes ship research-state (``funding_state`` ``research``); producing
a target gives the *capability* to surface/paper/(F004) trade it, never funding.

**Data source honesty:** the engine CODE is always real; the price DATA is real
when the VM ``WORKBENCH_DATA_ROOT`` unified prices + CN universe cover the A-share
attack universe, else absent (local / CI). ``meta.data_source`` is marked
honestly, and a run that cannot cover the universe fails as ``data_not_covered``
(actionable: refresh the data) rather than silently publishing an all-cash target.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any, Protocol

from sqlalchemy.orm import Session

from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)

if TYPE_CHECKING:
    from trade.backtest.cn_attack_momentum_quality.live import (  # type: ignore[import-untyped]
        CnAttackLiveTarget,
    )

logger = logging.getLogger(__name__)

_PRICES_SOURCE_REAL = "real"
_PRICES_SOURCE_FIXTURE = "fixture"

# The pseudo-symbol carrying the strategy's uninvested cash so the persisted
# target sums to 1.0 (the CN attack book holds a genuine cash buffer; A-shares
# have no SGOV-style cash proxy in this universe).
CN_ATTACK_CASH_SYMBOL = "CASH"
CN_ATTACK_SLEEVE = "cn_attack"
CN_ATTACK_CASH_SLEEVE = "cash"

# Error-kind codes the refresh worker / frontend map to a friendly message
# (mirrors regime_precompute — distinguish a data-coverage gap from a real bug).
ERROR_KIND_DATA_NOT_COVERED = "data_not_covered"
ERROR_KIND_SCORING = "scoring_error"

# ★ Spec §0 — the non-negotiable cn_attack honesty caveat. Denormalised onto every
# snapshot's master_meta so the surface (F003) can render the cn_attack-specific
# unvalidated / negative-OOS disclosure (超出通用研究徽章). Stable keys; the
# frontend reads these verbatim. NOT a return prediction — a truthful disclosure.
CN_ATTACK_RESEARCH_CAVEAT: dict[str, Any] = {
    "validated": False,
    "oos_result": "negative",
    "oos_cagr_range": "-14.7% (B081 引擎修真后 PIT)",
    "headline_zh": (
        "未经样本外验证：B081 引擎修真后（真实 100 股/手取整），去偏 PIT 样本外 "
        "CAGR −14.7%——原 B070 +28.4% 大半是分数股假象，修真后策略样本外亏损。"
    ),
    "headline_en": (
        "Unvalidated out-of-sample: after B081 engine-fidelity fixes (realistic "
        "100-share lots), de-biased PIT OOS CAGR is −14.7% — the apparent B070 "
        "+28.4% was largely a fractional-share artifact; the strategy loses OOS."
    ),
    "detail_zh": "advisory-only：系统只给建议，不自动下单、不预测收益；按它交易风险自负。",
    "detail_en": (
        "Advisory-only: the system only suggests; it does not auto-trade or predict "
        "returns. Trading on it is at your own risk."
    ),
    "backtest_ref": "docs/test-reports/B081-engine-fidelity-ab.md",
}


class CnAttackPrecomputeError(RuntimeError):
    """CN attack scoring could not produce a target (almost always a data gap).

    Raised when the available price / universe data cannot drive the (unchanged,
    tested) CN attack engine to a non-empty target — typically the unified prices
    file / CN PIT universe does not cover the A-share attack universe (local / CI,
    or a VM that has not refreshed). The refresh worker maps it to
    ``data_not_covered`` so the frontend shows an actionable "refresh the data"."""


@dataclass(frozen=True, slots=True)
class CnAttackTargetResult:
    """Output of the CN attack scoring: current target + attribution + meta.

    ``target_weights`` here INCLUDES the explicit cash row, so it already sums to
    1.0 and the producer persists it row-for-row (uniform with regime)."""

    as_of_date: date
    target_weights: dict[str, float]  # symbol → weight (cash row included; sums 1.0)
    symbol_sleeve: dict[str, str]
    meta: dict[str, Any]


class CnAttackScoreFn(Protocol):
    def __call__(self) -> CnAttackTargetResult: ...


@dataclass(frozen=True, slots=True)
class CnAttackPrecomputeSummary:
    saved: int
    as_of_date: date | None
    data_source: str | None
    error: str | None
    error_kind: str | None = None


def _classify_data_source() -> str:
    """``real`` when the VM data root carries the unified prices + CN universe,
    else ``fixture`` (local / CI fall back to bundled data)."""

    from trade.data.cn_attack_universe import (  # type: ignore[import-untyped]
        DEFAULT_CN_UNIVERSE_PATH,
    )
    from trade.data.data_root import (  # type: ignore[import-untyped]
        data_root_override,
        unified_cn_universe_path,
        unified_prices_path,
    )
    from trade.data.us_quality_universe import (  # type: ignore[import-untyped]
        UNIFIED_PRICES_PATH,
    )

    if (
        data_root_override() is not None
        and unified_prices_path(UNIFIED_PRICES_PATH).exists()
        and unified_cn_universe_path(DEFAULT_CN_UNIVERSE_PATH).exists()
    ):
        return _PRICES_SOURCE_REAL
    return _PRICES_SOURCE_FIXTURE


def score_cn_attack_target(
    *,
    strategy_id: str,
    factor_variant: str,
    caveat: dict[str, Any] | None = None,
) -> CnAttackTargetResult:
    """Load the A-share data and compute the CN attack mode's current target.

    **The only place trade is imported for production scoring.** Runs the daily
    band driver (``compute_cn_attack_live_target``) over the on-disk unified data,
    appends the explicit cash row (head trap), and packs the profit-take + the
    ★OOS honesty caveat into the meta. Raises :class:`CnAttackPrecomputeError`
    (→ ``data_not_covered``) when the data cannot cover the universe — never
    publishes an all-cash degenerate target (B066 §29 no-silent-degenerate).

    B080 F001: ``caveat`` (the DB ``oos_verification_card`` row resolved by the
    caller) overrides the in-code fallback when supplied; ``None`` → byte-identical
    to the pre-B080 ``CN_ATTACK_RESEARCH_CAVEAT``.
    """

    from trade.backtest.cn_attack_momentum_quality.engine import (  # type: ignore[import-untyped]
        CnBacktestError,
    )
    from trade.backtest.cn_attack_momentum_quality.live import (
        compute_cn_attack_live_target,
    )
    from trade.strategies.cn_attack_momentum_quality.parameters import (  # type: ignore[import-untyped]
        CnAttackParameters,
    )

    data_source = _classify_data_source()
    parameters = CnAttackParameters(factor_variant=factor_variant)
    try:
        live = compute_cn_attack_live_target(parameters)
    except CnBacktestError as exc:
        # Empty prices / < 2 trading days inside the warmed window → the A-share
        # data does not cover the attack universe (actionable: refresh the data).
        raise CnAttackPrecomputeError(
            f"CN attack data does not cover the universe ({exc}). Run the "
            "A-share price + CN universe refresh to populate the unified data."
        ) from exc

    if not live.target_weights:
        # No invested names = an all-cash degenerate target. For an attack strategy
        # on a covered universe this never happens; it means the data does not cover
        # the universe (local / CI). Fail actionable rather than publish 100% cash.
        raise CnAttackPrecomputeError(
            "CN attack produced an empty (all-cash) target — the unified prices / "
            "CN PIT universe do not cover the A-share attack universe. Run the "
            "A-share data refresh."
        )

    return _build_target_result(strategy_id, factor_variant, data_source, live, caveat)


def _build_target_result(
    strategy_id: str,
    factor_variant: str,
    data_source: str,
    live: CnAttackLiveTarget,
    caveat: dict[str, Any] | None = None,
) -> CnAttackTargetResult:
    target_weights: dict[str, float] = dict(live.target_weights)
    symbol_sleeve = {symbol: CN_ATTACK_SLEEVE for symbol in target_weights}
    if live.cash_weight > 0:
        target_weights[CN_ATTACK_CASH_SYMBOL] = live.cash_weight
        symbol_sleeve[CN_ATTACK_CASH_SYMBOL] = CN_ATTACK_CASH_SLEEVE

    meta: dict[str, Any] = {
        "data_source": data_source,
        "prices_source": data_source,
        "strategy_id": strategy_id,
        "factor_variant": factor_variant,
        "cadence": "daily",
        "signal_date": live.signal_date.isoformat(),
        "rebalanced": live.rebalanced,
        "no_trade_band": live.no_trade_band,
        "would_be_turnover": round(live.would_be_turnover, 6),
        "top_n": live.top_n,
        # ★获利了结 landed: the names rotated out of the top-N today (the diff
        # "卖到零" list reads this to explain why a name leaves).
        "profit_take": list(live.profit_take),
        "cash_weight": live.cash_weight,
        # B080 F002 — raw composite factor score per selected name (top-N by score),
        # forward-accumulated so the monitoring rolling-IC can key off the true
        # signal. Pure added meta key (zero regression; empty on a hold-day).
        "signal_scores": dict(
            sorted(live.signal_scores.items(), key=lambda kv: -kv[1])[: live.top_n]
        ),
        # ★ Spec §0 honesty (non-negotiable) — the surface renders this.
        # B080 F001: prefer the DB card (caveat) when the caller resolved one;
        # no card → byte-identical fallback to the in-code constant.
        "research_only": True,
        "research_caveat": dict(
            caveat if caveat is not None else CN_ATTACK_RESEARCH_CAVEAT
        ),
    }
    return CnAttackTargetResult(
        as_of_date=live.as_of_date,
        target_weights=target_weights,
        symbol_sleeve=symbol_sleeve,
        meta=meta,
    )


def run_cn_attack_precompute(
    session: Session,
    strategy_id: str,
    *,
    factor_variant: str,
    score_fn: CnAttackScoreFn | None = None,
    computed_at: datetime | None = None,
) -> CnAttackPrecomputeSummary:
    """Score the current CN attack target and persist it into the target layer.

    ``score_fn`` is injectable so tests supply a fake target without importing
    trade / loading prices. Best-effort: on a scoring failure the snapshot is left
    untouched (the request path stays graceful on the previous target). Persists
    under ``strategy_id`` so it never tramples another mode's rows (the repo delete
    is scoped by strategy_id).
    """

    # B080 F001 — resolve the DB-ized OOS red card here (the session owner); a
    # missing row → None → byte-identical fallback to CN_ATTACK_RESEARCH_CAVEAT.
    # An injected ``score_fn`` (tests) bypasses this and never hits the DB.
    card = OosVerificationCardRepository(session).get_card(strategy_id)
    fn = score_fn or (
        lambda: score_cn_attack_target(
            strategy_id=strategy_id, factor_variant=factor_variant, caveat=card
        )
    )
    try:
        result = fn()
    except CnAttackPrecomputeError as exc:
        logger.warning("cn_attack_precompute_data_not_covered: %s", exc)
        return CnAttackPrecomputeSummary(
            saved=0,
            as_of_date=None,
            data_source=None,
            error=str(exc),
            error_kind=ERROR_KIND_DATA_NOT_COVERED,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort job; never crash the timer
        logger.exception("cn_attack_precompute_failed")
        return CnAttackPrecomputeSummary(
            saved=0,
            as_of_date=None,
            data_source=None,
            error=str(exc),
            error_kind=ERROR_KIND_SCORING,
        )

    data_source = result.meta.get("data_source")
    rebalanced = bool(result.meta.get("rebalanced"))
    rows: list[dict[str, Any]] = []
    for symbol, weight in result.target_weights.items():
        sleeve = result.symbol_sleeve.get(symbol, CN_ATTACK_SLEEVE)
        rows.append(
            {
                "symbol": symbol,
                "sleeve": sleeve,
                "target_weight": weight,
                "rationale": _cn_attack_rationale(
                    symbol, sleeve, result.meta, rebalanced
                ),
            }
        )

    repo = RecommendationSnapshotRepository(session)
    saved = repo.save_batch(
        strategy_id=strategy_id,
        as_of_date=result.as_of_date,
        rows=rows,
        master_meta=result.meta,
        computed_at=computed_at or datetime.now(UTC),
    )
    session.commit()
    logger.info(
        "cn_attack_precompute_done",
        extra={
            "strategy_id": strategy_id,
            "as_of_date": result.as_of_date.isoformat(),
            "saved": len(saved),
            "data_source": data_source,
            "rebalanced": rebalanced,
        },
    )
    return CnAttackPrecomputeSummary(
        saved=len(saved),
        as_of_date=result.as_of_date,
        data_source=data_source,
        error=None,
    )


def _cn_attack_rationale(
    symbol: str,
    sleeve: str,
    meta: dict[str, Any],
    rebalanced: bool,
) -> str:
    """Deterministic Chinese rationale for one CN attack target row (research-state).

    Grounded in the factor variant + the band decision — no LLM, no return
    prediction (spec §0 honesty). The surface marks the whole mode 研究态; this line
    is the per-position "why it is held". The 获利了结 / 跌出 top-N list rides in
    ``master_meta.profit_take`` (those names are SOLD → they have no target row); the
    position-diff "卖到零" surface renders it."""

    if sleeve == CN_ATTACK_CASH_SLEEVE:
        return "现金缓冲（未投足额）：研究态 advisory，不自动下单、非收益预测。"
    variant_label = (
        "质量过滤+动量" if meta.get("factor_variant") == "quality_momentum" else "纯动量"
    )
    band_note = "今日触发调仓" if rebalanced else "不动区内持有（让赢家奔跑）"
    return (
        f"{symbol}（{variant_label}）：A股 进攻型选股入选（{band_note}）；"
        "研究态 advisory，未经样本外验证，非收益预测。"
    )


__all__ = [
    "CN_ATTACK_CASH_SYMBOL",
    "CN_ATTACK_RESEARCH_CAVEAT",
    "ERROR_KIND_DATA_NOT_COVERED",
    "ERROR_KIND_SCORING",
    "CnAttackPrecomputeError",
    "CnAttackPrecomputeSummary",
    "CnAttackTargetResult",
    "run_cn_attack_precompute",
    "score_cn_attack_target",
]
