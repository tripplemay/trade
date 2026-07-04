"""B080 F003 — CPCV-lite split generator (pure, testable).

The frozen re-validation reports the strategy's out-of-sample behaviour over K=4
quarter-staggered OOS windows (not one contiguous 70/30 split), each preceded by a
1-month purge gap, then reports the per-split OOS metric distribution. This is
**deliberately NOT full combinatorial-purged CV** (that would evaluate every
train/test combination) — it is a lightweight staggered walk-forward, and every
consumer (the md report, the trial_registry ``oos_split`` field) must label it so.

Because the cn_attack strategy has **no fitted parameters** (it is a rule, not a
trained model), the "in-sample" region only provides the momentum lookback data —
so the 1-month purge is enforced simply by starting each OOS window at least a
month after its IS region ends. Each split's backtest runs fresh over its own OOS
window; this module only decides the window boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

# Human-readable label carried into every report + the trial_registry oos_split
# field so the "not full CPCV" honesty (spec §2 F003 / §3) never gets lost.
CPCV_LITE_LABEL = "CPCV-lite: K=4 quarter-staggered OOS + 1mo purge (not full CPCV)"

_DEFAULT_K = 4
_PURGE_DAYS = 30


@dataclass(frozen=True, slots=True)
class Split:
    """One CPCV-lite fold: an IS region, a purge gap, then the OOS window that is
    actually scored."""

    index: int
    is_start: date
    is_end: date
    oos_start: date
    oos_end: date


def cpcv_lite_splits(
    start: date,
    end: date,
    *,
    k: int = _DEFAULT_K,
    purge_days: int = _PURGE_DAYS,
) -> list[Split]:
    """K quarter-staggered ``Split``s tiling ``[start, end]``.

    The span is divided into ``k + 1`` equal blocks; blocks ``1..k`` are the OOS
    windows (each a staggered ~quarter of the span), and each OOS window is
    preceded by the growing IS region ``[start, oos_start - purge_days]`` — the
    purge gap guarantees no IS bar sits within a month of the scored window.
    Returns ``[]`` when the span is too short to carve ``k`` purged folds (honest
    degrade — the caller then falls back to the single contiguous split).
    """

    total_days = (end - start).days
    if total_days <= 0 or k < 1:
        return []
    block = total_days // (k + 1)
    if block <= purge_days:
        return []  # too short to fit a purge gap inside each IS→OOS step
    splits: list[Split] = []
    for i in range(1, k + 1):
        oos_start = start + timedelta(days=block * i)
        oos_end = end if i == k else start + timedelta(days=block * (i + 1))
        is_end = oos_start - timedelta(days=purge_days)
        if is_end <= start:
            continue  # not enough IS history before this fold's purge gap
        splits.append(
            Split(
                index=i,
                is_start=start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
            )
        )
    return splits
