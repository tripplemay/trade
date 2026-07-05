"""B082 F003 — 红利低波 defensive-sleeve advisory target precompute (the producer).

Imports the ``trade`` package and runs the **existing, unchanged** F002 spread
signal (``trade.strategies.cn_dividend_lowvol.signal``) over the frozen daily CSVs
the F001 data-refresh job writes under ``<data_root>/snapshots/dividend_lowvol/``,
then publishes the sleeve's current target — the dividend-low-vol ETF at the frozen
three-tier 利差档位 weight, plus a CASH row for the uninvested residual — into the
generic target layer (``recommendation_snapshot`` keyed by ``strategy_id``). The daily
``workbench-cn-dividend-lowvol`` timer (F003) runs this; the request path reads the DB
(never imports trade — §12.10.2 AST guard).

Cadence honesty (spec §0 monitor-daily / act-monthly / 不动区): the timer runs DAILY
so the published tier is fresh, but the executed weight is the tier at the latest
**completed** month-end 利差 (a mid-month spread move does NOT flip the target — that is
the 不动区 / monthly-execution rule). The current-day spread + would-be tier ride in the
meta as a monitor observation, never as the executed target.

Three things this layer must get right (mirrors cn_attack_precompute):

1. **CASH row → sum 1.0 (the head trap).** The sleeve is only fractionally invested
   below the 满配 tier, so we append an explicit ``CASH`` row = ``1 − etf_weight`` and
   the persisted target is fully allocated (``save_batch`` refuses a set that misses 1.0).
2. **利差档位 landed.** The executed tier + the driving 股息率 / 利差 / thresholds are
   written into ``master_meta`` so the surface shows *why* the sleeve is at 满配/半配/低配.
3. **★OOS honesty (spec §3 不变量, non-negotiable).** Every snapshot's ``master_meta``
   carries the dividend-lowvol research caveat (the DB ``oos_verification_card`` row when
   present, B080 mechanism; else the F002 in-code fallback constant) so the surface renders
   it honestly — never an implication that this is a validated, funded edge.

Boundary (r-c): deterministic quant target precompute, read-only — it writes
``recommendation_snapshot`` and never touches broker / order-ticket / execution surfaces.
The mode ships research-state (``funding_state`` ``research``); producing a target gives the
*capability* to surface/paper it, never funding.

**Data source honesty:** the signal CODE is always real; the DATA is real when the VM
``WORKBENCH_DATA_ROOT`` snapshots/dividend_lowvol CSVs are present (F001 daily refresh),
else absent (local / CI). A run that cannot read the frozen series fails as
``data_not_covered`` (actionable: run the A-share dividend-lowvol data refresh) rather than
silently publishing an all-cash target.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.orm import Session

from workbench_api.data_refresh.cn_dividend_lowvol import DIVIDEND_LOWVOL_SUBDIR
from workbench_api.db.repositories.oos_verification_card import (
    OosVerificationCardRepository,
)
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)
from workbench_api.monitoring.trial_backfill_b082 import (
    CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT,
)
from workbench_api.strategy_modes.registry import CN_DIVIDEND_LOWVOL_STRATEGY_ID

logger = logging.getLogger(__name__)

_PRICES_SOURCE_REAL = "real"

# The tradeable dividend-low-vol ETF the sleeve holds (华泰柏瑞中证红利低波动 ETF). The
# F001 snapshot fetches its sina bars under symbol ``sh512890``; the published target /
# paper book key is the exchange-suffixed ``512890.SH`` (A-share convention).
CN_DIVIDEND_LOWVOL_ETF_SYMBOL = "512890.SH"
CN_DIVIDEND_LOWVOL_SLEEVE = "dividend_lowvol"
CN_DIVIDEND_LOWVOL_CASH_SYMBOL = "CASH"
CN_DIVIDEND_LOWVOL_CASH_SLEEVE = "cash"

_WEIGHT_ROUND_DIGITS = 6

# The three CSVs the signal needs (written by workbench_api.data_refresh.cn_dividend_lowvol):
# the total-return index (H20269) and price index (H30269) reconstruct the 股息率, and the
# 10Y treasury yield gives the 利差. The ETF bars are the implementability layer only (F002),
# not the return 口径, so the live tier is computed on the index 口径 like the backtest.
_TR_INDEX_CSV = "index_h20269"
_PR_INDEX_CSV = "index_h30269"
_YIELD_CSV = "cn_10y_yield"

# Error-kind codes the refresh worker / frontend map to a friendly message (mirrors
# cn_attack / regime — distinguish a data-coverage gap from a real bug).
ERROR_KIND_DATA_NOT_COVERED = "data_not_covered"
ERROR_KIND_SCORING = "scoring_error"

# Executed-tier labels (stable keys the surface maps to 满配/半配/低配).
_TIER_FULL = "full"
_TIER_HALF = "half"
_TIER_LOW = "low"


class CnDividendLowvolPrecomputeError(RuntimeError):
    """The dividend-lowvol signal could not produce a target (almost always a data gap).

    Raised when the frozen ``snapshots/dividend_lowvol`` CSVs are absent or too short to
    reconstruct the 股息率 / 利差 (local / CI, or a VM that has not refreshed). The refresh
    worker maps it to ``data_not_covered`` so the frontend shows an actionable
    "run the A-share dividend-lowvol data refresh"."""


@dataclass(frozen=True, slots=True)
class CnDividendLowvolTargetResult:
    """Output of the dividend-lowvol scoring: current target + attribution + meta.

    ``target_weights`` here INCLUDES the explicit cash row (when below 满配), so it already
    sums to 1.0 and the producer persists it row-for-row (uniform with cn_attack / regime)."""

    as_of_date: date
    target_weights: dict[str, float]  # symbol → weight (cash row included; sums 1.0)
    symbol_sleeve: dict[str, str]
    meta: dict[str, Any]


class CnDividendLowvolScoreFn(Protocol):
    def __call__(self) -> CnDividendLowvolTargetResult: ...


@dataclass(frozen=True, slots=True)
class CnDividendLowvolPrecomputeSummary:
    saved: int
    as_of_date: date | None
    data_source: str | None
    error: str | None
    error_kind: str | None = None


def _dividend_lowvol_data_dir() -> Path | None:
    """The VM ``snapshots/dividend_lowvol`` directory, or ``None`` on local / CI.

    Trusts the VM data-root override (the F001 refresh writes the CSVs under it); a
    missing override means the frozen series are not on this host (→ data_not_covered)."""

    from trade.data.data_root import data_root_override  # type: ignore[import-untyped]

    root: Path | None = data_root_override()
    if root is None:
        return None
    return root.joinpath(*DIVIDEND_LOWVOL_SUBDIR)


def _load_series(data_dir: Path, name: str, value_col: str) -> Any:
    """Read one date-indexed ``value_col`` series from ``<data_dir>/<name>.csv``.

    Raises :class:`CnDividendLowvolPrecomputeError` when the CSV is absent (a coverage
    gap, not a bug) so the caller degrades to ``data_not_covered``."""

    import pandas as pd  # type: ignore[import-untyped]

    path = data_dir.joinpath(f"{name}.csv")
    if not path.is_file():
        raise CnDividendLowvolPrecomputeError(
            f"dividend-lowvol series {name!r} not found at {path} — run the A-share "
            "dividend-lowvol data refresh to populate snapshots/dividend_lowvol/."
        )
    frame = pd.read_csv(path, parse_dates=["date"])
    return frame.set_index("date")[value_col].astype(float).sort_index()


def _tier_label(weight: float, params: Any) -> str:
    """Map an executed tier weight to its stable label (满配/半配/低配)."""

    if weight >= params.full_weight:
        return _TIER_FULL
    if weight >= params.half_weight:
        return _TIER_HALF
    return _TIER_LOW


def score_cn_dividend_lowvol_target(
    *,
    strategy_id: str = CN_DIVIDEND_LOWVOL_STRATEGY_ID,
    caveat: dict[str, Any] | None = None,
    as_of: date | None = None,
) -> CnDividendLowvolTargetResult:
    """Load the frozen dividend-lowvol series and compute the sleeve's current target.

    **The only place trade is imported for production scoring.** Reconstructs the index
    股息率 (TR−PR), computes the 利差 vs the 10Y yield, and takes the frozen three-tier
    weight at the latest COMPLETED month-end (act-monthly / 不动区). Appends the CASH row
    (head trap) and packs the tier + ★OOS honesty caveat into the meta. Raises
    :class:`CnDividendLowvolPrecomputeError` (→ ``data_not_covered``) when the CSVs cannot
    be read / are too short — never publishes an all-cash degenerate target.

    ``caveat`` (the DB ``oos_verification_card`` row resolved by the caller) overrides the
    in-code fallback when supplied; ``None`` → the F002 ``CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT``.
    """

    import pandas as pd
    from trade.strategies.cn_dividend_lowvol.parameters import (  # type: ignore[import-untyped]
        CnDividendLowvolParameters,
    )
    from trade.strategies.cn_dividend_lowvol.signal import (  # type: ignore[import-untyped]
        compute_spread,
        reconstruct_dividend_yield,
    )

    data_dir = _dividend_lowvol_data_dir()
    if data_dir is None or not data_dir.is_dir():
        raise CnDividendLowvolPrecomputeError(
            "dividend-lowvol snapshot directory is absent (WORKBENCH_DATA_ROOT unset or "
            "the F001 refresh has not run) — run the A-share dividend-lowvol data refresh."
        )

    params = CnDividendLowvolParameters()
    tr = _load_series(data_dir, _TR_INDEX_CSV, "close")
    pr = _load_series(data_dir, _PR_INDEX_CSV, "close")
    y10 = _load_series(data_dir, _YIELD_CSV, "yield")

    divy = reconstruct_dividend_yield(tr, pr, params.dividend_yield_lookback_days)
    spread = compute_spread(divy, y10)
    if spread.empty:
        raise CnDividendLowvolPrecomputeError(
            "dividend-lowvol 利差 series is empty after reconstruction — the frozen index "
            "/ yield history is too short. Run the A-share dividend-lowvol data refresh."
        )

    run_date = as_of or datetime.now(UTC).date()
    # Month-end 利差 (execution cadence); publish the latest COMPLETED month-end so a
    # mid-month spread move never flips the executed target (act-monthly / 不动区).
    monthly_spread = spread.resample("ME").last().dropna()
    completed = monthly_spread[monthly_spread.index <= pd.Timestamp(run_date)]
    if completed.empty:
        raise CnDividendLowvolPrecomputeError(
            "no completed month-end 利差 on/before the run date — insufficient history."
        )

    as_of_date = completed.index[-1].date()
    exec_spread = float(completed.iloc[-1])
    etf_weight = float(params.target_weight_for_spread(exec_spread))
    # The 股息率 that drove the executed tier (index 口径, at the same month-end).
    monthly_divy = divy.resample("ME").last().dropna()
    exec_divy = monthly_divy.reindex([completed.index[-1]]).iloc[0]
    exec_divy_val = float(exec_divy) if exec_divy == exec_divy else None  # NaN-safe

    # Daily monitor observation (never the executed target): today's spread + would-be tier.
    monitor_spread = float(spread.iloc[-1])
    monitor_weight = float(params.target_weight_for_spread(monitor_spread))

    meta: dict[str, Any] = {
        "data_source": _PRICES_SOURCE_REAL,
        "prices_source": _PRICES_SOURCE_REAL,
        "strategy_id": strategy_id,
        "cadence": "monthly",
        "signal_date": as_of_date.isoformat(),
        # Executed tier (the published target): tier label + driving 利差 / 股息率.
        "tier": _tier_label(etf_weight, params),
        "etf_weight": round(etf_weight, _WEIGHT_ROUND_DIGITS),
        "spread_pct": round(exec_spread, 4),
        "dividend_yield_pct": (
            round(exec_divy_val, 4) if exec_divy_val is not None else None
        ),
        # Frozen (spec-先验) thresholds — denormalised so the surface can explain the rule
        # without re-deriving it (禁止扫参: these are READ from the frozen params, never tuned).
        "saturated_spread_pct": params.saturated_spread_pct,
        "half_spread_pct": params.half_spread_pct,
        "etf_symbol": CN_DIVIDEND_LOWVOL_ETF_SYMBOL,
        # Daily monitor observation (下一次月度执行的 would-be 档位; not yet executed).
        "monitor_date": spread.index[-1].date().isoformat(),
        "monitor_spread_pct": round(monitor_spread, 4),
        "monitor_would_be_tier": _tier_label(monitor_weight, params),
        # ★ Spec §3 honesty (non-negotiable) — the surface renders this. Prefer the DB card
        # (caveat) when the caller resolved one; no card → byte-identical fallback constant.
        "research_only": True,
        "research_caveat": dict(
            caveat if caveat is not None else CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT
        ),
    }

    target_weights: dict[str, float] = {
        CN_DIVIDEND_LOWVOL_ETF_SYMBOL: round(etf_weight, _WEIGHT_ROUND_DIGITS)
    }
    symbol_sleeve: dict[str, str] = {
        CN_DIVIDEND_LOWVOL_ETF_SYMBOL: CN_DIVIDEND_LOWVOL_SLEEVE
    }
    cash_weight = round(1.0 - etf_weight, _WEIGHT_ROUND_DIGITS)
    if cash_weight > 0:
        target_weights[CN_DIVIDEND_LOWVOL_CASH_SYMBOL] = cash_weight
        symbol_sleeve[CN_DIVIDEND_LOWVOL_CASH_SYMBOL] = CN_DIVIDEND_LOWVOL_CASH_SLEEVE

    return CnDividendLowvolTargetResult(
        as_of_date=as_of_date,
        target_weights=target_weights,
        symbol_sleeve=symbol_sleeve,
        meta=meta,
    )


def run_cn_dividend_lowvol_precompute(
    session: Session,
    strategy_id: str = CN_DIVIDEND_LOWVOL_STRATEGY_ID,
    *,
    score_fn: CnDividendLowvolScoreFn | None = None,
    computed_at: datetime | None = None,
) -> CnDividendLowvolPrecomputeSummary:
    """Score the current dividend-lowvol target and persist it into the target layer.

    ``score_fn`` is injectable so tests supply a fake target without importing trade /
    reading CSVs. Best-effort: on a scoring failure the snapshot is left untouched (the
    request path stays graceful on the previous target). Persists under ``strategy_id`` so
    it never tramples another mode's rows (the repo delete is scoped by strategy_id).
    """

    # B080 mechanism — resolve the DB-ized OOS red card here (the session owner); a missing
    # row → None → byte-identical fallback to CN_DIVIDEND_LOWVOL_RESEARCH_CAVEAT. An injected
    # ``score_fn`` (tests) bypasses this and never hits the DB.
    card = OosVerificationCardRepository(session).get_card(strategy_id)
    fn = score_fn or (
        lambda: score_cn_dividend_lowvol_target(strategy_id=strategy_id, caveat=card)
    )
    try:
        result = fn()
    except CnDividendLowvolPrecomputeError as exc:
        logger.warning("cn_dividend_lowvol_precompute_data_not_covered: %s", exc)
        return CnDividendLowvolPrecomputeSummary(
            saved=0,
            as_of_date=None,
            data_source=None,
            error=str(exc),
            error_kind=ERROR_KIND_DATA_NOT_COVERED,
        )
    except Exception as exc:  # noqa: BLE001 — best-effort job; never crash the timer
        logger.exception("cn_dividend_lowvol_precompute_failed")
        return CnDividendLowvolPrecomputeSummary(
            saved=0,
            as_of_date=None,
            data_source=None,
            error=str(exc),
            error_kind=ERROR_KIND_SCORING,
        )

    data_source = result.meta.get("data_source")
    rows: list[dict[str, Any]] = []
    for symbol, weight in result.target_weights.items():
        sleeve = result.symbol_sleeve.get(symbol, CN_DIVIDEND_LOWVOL_SLEEVE)
        rows.append(
            {
                "symbol": symbol,
                "sleeve": sleeve,
                "target_weight": weight,
                "rationale": _cn_dividend_lowvol_rationale(symbol, sleeve, result.meta),
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
        "cn_dividend_lowvol_precompute_done",
        extra={
            "strategy_id": strategy_id,
            "as_of_date": result.as_of_date.isoformat(),
            "saved": len(saved),
            "data_source": data_source,
            "tier": result.meta.get("tier"),
        },
    )
    return CnDividendLowvolPrecomputeSummary(
        saved=len(saved),
        as_of_date=result.as_of_date,
        data_source=data_source,
        error=None,
    )


def _cn_dividend_lowvol_rationale(
    symbol: str, sleeve: str, meta: dict[str, Any]
) -> str:
    """Deterministic Chinese rationale for one dividend-lowvol target row (research-state).

    Grounded in the executed 利差档位 — no LLM, no return prediction (spec §3 honesty). The
    surface marks the whole mode 研究态; this line is the per-position "why it is held"."""

    if sleeve == CN_DIVIDEND_LOWVOL_CASH_SLEEVE:
        return "现金缓冲（利差未满配的余额）：研究态 advisory，不自动下单、非收益预测。"
    tier_zh = {_TIER_FULL: "满配", _TIER_HALF: "半配", _TIER_LOW: "低配"}.get(
        str(meta.get("tier")), str(meta.get("tier"))
    )
    spread = meta.get("spread_pct")
    return (
        f"{symbol}（红利低波防守腿）：股息率−十年国债利差 {spread}% → {tier_zh}"
        "（≥2.5% 满配 / 1.5-2.5% 半配 / <1.5% 低配，spec 先验规则、禁扫参）；"
        "月度执行 / 不动区；研究态 advisory，未经样本外验证，规则无收益增量，非收益预测。"
    )


__all__ = [
    "CN_DIVIDEND_LOWVOL_CASH_SYMBOL",
    "CN_DIVIDEND_LOWVOL_ETF_SYMBOL",
    "ERROR_KIND_DATA_NOT_COVERED",
    "ERROR_KIND_SCORING",
    "CnDividendLowvolPrecomputeError",
    "CnDividendLowvolPrecomputeSummary",
    "CnDividendLowvolTargetResult",
    "run_cn_dividend_lowvol_precompute",
    "score_cn_dividend_lowvol_target",
]
