"""B111 F003 (P0-3) — target-staleness alert (catch the FROZEN target).

The P0-3 root cause was invisible for 7 weeks: ``regime_adaptive``'s published
target froze on 2026-05-29 (the monthly timer missed July after a migration) and
nothing went red — the monitoring job explicitly excluded master + regime. This
module turns "the published target has not advanced" into a pure, testable
verdict + alert the weekly/daily monitoring job asserts.

Unlike :mod:`workbench_api.data_refresh.freshness` (business-day aged, for the
*daily* price/recommendation snapshots), a regime/master target advances only
MONTHLY (regime) or per quarter-end (master), so staleness is measured in plain
CALENDAR days with a threshold set past a full month plus slack: 45 days catches
the P0-3 freeze (49 days by the time it surfaced) while a normal monthly refresh
(~30 days) never trips it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

# A published target older than this many CALENDAR days has not advanced across
# a normal monthly refresh — the P0-3 freeze (49 days) trips it; a healthy
# ~30-day monthly cadence does not.
TARGET_STALENESS_ALERT_DAYS = 45


@dataclass(frozen=True, slots=True)
class TargetStalenessVerdict:
    """Whether a strategy's published target has advanced recently."""

    strategy_id: str
    as_of_date: date | None
    age_days: int | None
    threshold_days: int
    is_stale: bool
    reason: str


def assess_target_staleness(
    strategy_id: str,
    as_of_date: date | None,
    now: date,
    *,
    threshold_days: int = TARGET_STALENESS_ALERT_DAYS,
) -> TargetStalenessVerdict:
    """Verdict for a strategy's most-recent published ``as_of_date``.

    A missing ``as_of`` (never published) is stale — an absent target is a freeze
    too. Otherwise stale iff its calendar-day age exceeds ``threshold_days``."""

    if as_of_date is None:
        return TargetStalenessVerdict(
            strategy_id=strategy_id,
            as_of_date=None,
            age_days=None,
            threshold_days=threshold_days,
            is_stale=True,
            reason=f"{strategy_id}: no published target on record (never written)",
        )
    age = (now - as_of_date).days
    is_stale = age > threshold_days
    return TargetStalenessVerdict(
        strategy_id=strategy_id,
        as_of_date=as_of_date,
        age_days=age,
        threshold_days=threshold_days,
        is_stale=is_stale,
        reason=(
            f"{strategy_id}: as_of={as_of_date.isoformat()} age={age}d "
            f"(threshold={threshold_days}d) → {'STALE' if is_stale else 'fresh'}"
        ),
    )
