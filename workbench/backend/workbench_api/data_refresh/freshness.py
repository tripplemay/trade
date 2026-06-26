"""B078 F002 — data-freshness gate (catch the SILENT freeze).

The B078 root cause was invisible for four days: ``data-refresh.service`` hung,
A-share prices / universe / recommendations all froze on 2026-06-22, and nothing
went red — the precompute kept re-emitting the same stale snapshot and the paper
book dutifully "tracked" a frozen target. That silence is the bug this module
exists to break. It turns three freshness signals into pure, testable verdicts a
CI acceptance test and a production healthcheck can both assert:

1. ``recommendation_snapshot`` ``as_of`` is recent (the published target advances).
2. The A-share ``price_snapshot`` is recent (the daily 命门 advances).
3. ``data-refresh.service`` is not stuck ``activating`` beyond a sane bound (the
   stuck-``activating`` state that the B078 F001 ``TimeoutStartSec`` watchdog now
   also kills — this is the monitoring counterpart).

Freshness is measured in **business days** (Mon-Fri) so a normal weekend never
trips the gate. The honest residual: a long market holiday (国庆 / 春节) can
push the age past the threshold and raise a benign WARNING — acceptable for a
monitoring signal, and far better than a four-day silent freeze in a normal week.
Thresholds are parameters so ops can tune them; the defaults catch the B078
freeze (4 business days) with two business days of slack.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from workbench_api.db.models.price_snapshot import PriceSnapshot
from workbench_api.db.repositories.recommendation_snapshot import (
    RecommendationSnapshotRepository,
)

# A snapshot whose as_of is older than this many BUSINESS days is stale. The
# B078 freeze was 4 business days; 3 catches it with weekend immunity + 2 days
# of slack for normal operation.
DEFAULT_MAX_SNAPSHOT_AGE_BUSINESS_DAYS = 3

# A oneshot data-refresh stuck "activating" beyond this is hung. A healthy wide
# refresh is ~33min (B075) and the B078 F001 watchdog kills it at 90min, so >2h
# activating is unambiguously pathological.
DEFAULT_MAX_ACTIVATING = timedelta(hours=2)


def business_days_between(start: date, end: date) -> int:
    """Count weekdays (Mon-Fri) in the half-open interval ``(start, end]``.

    ``0`` when ``end <= start`` (same-day / future as_of is fresh, never stale).
    A Friday→Monday gap is 1 business day, so a normal weekend never ages a
    snapshot past a one-business-day check."""

    if end <= start:
        return 0
    count = 0
    cursor = start
    while cursor < end:
        cursor += timedelta(days=1)
        if cursor.weekday() < 5:  # Mon=0 .. Fri=4
            count += 1
    return count


@dataclass(frozen=True, slots=True)
class FreshnessVerdict:
    """Whether a dated artifact is fresh, with the business-day age + reason."""

    label: str
    as_of: date | None
    age_business_days: int | None
    threshold: int
    is_fresh: bool
    reason: str


def assess_as_of_freshness(
    label: str,
    as_of: date | None,
    now: date,
    *,
    max_business_days: int = DEFAULT_MAX_SNAPSHOT_AGE_BUSINESS_DAYS,
) -> FreshnessVerdict:
    """Verdict for a dated artifact (recommendation / price snapshot ``as_of``).

    A missing ``as_of`` (never written) is NOT fresh — an absent artifact is a
    freeze too. Otherwise stale iff its business-day age exceeds the threshold."""

    if as_of is None:
        return FreshnessVerdict(
            label=label,
            as_of=None,
            age_business_days=None,
            threshold=max_business_days,
            is_fresh=False,
            reason=f"{label}: no as_of on record (never written)",
        )
    age = business_days_between(as_of, now)
    is_fresh = age <= max_business_days
    reason = (
        f"{label}: as_of={as_of.isoformat()} age={age}bd "
        f"(threshold={max_business_days}bd) → {'fresh' if is_fresh else 'STALE'}"
    )
    return FreshnessVerdict(
        label=label,
        as_of=as_of,
        age_business_days=age,
        threshold=max_business_days,
        is_fresh=is_fresh,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class ServiceVerdict:
    """Whether the data-refresh service is wedged in the ``activating`` state."""

    is_stuck: bool
    reason: str


def assess_service_activating(
    active_state: str,
    activating_since: datetime | None,
    now: datetime,
    *,
    max_activating: timedelta = DEFAULT_MAX_ACTIVATING,
) -> ServiceVerdict:
    """Verdict for a systemd ``Active:`` state (parsed from ``systemctl show``).

    Stuck iff the unit is ``activating`` and has been so for longer than
    ``max_activating`` — exactly the B078 state (``activating`` for 3 days). Any
    other state (``active`` / ``inactive`` / ``failed``) or a short, healthy
    ``activating`` window is not stuck."""

    if active_state != "activating":
        return ServiceVerdict(False, f"service active_state={active_state!r} (not activating)")
    if activating_since is None:
        return ServiceVerdict(False, "service activating but start time unknown")
    elapsed = now - activating_since
    is_stuck = elapsed > max_activating
    return ServiceVerdict(
        is_stuck,
        f"service activating for {elapsed} (max {max_activating}) → "
        f"{'STUCK' if is_stuck else 'ok'}",
    )


# --------------------------------------------------------------------------- #
# Thin read-only DB helpers (the freshness inputs the verdicts above consume)
# --------------------------------------------------------------------------- #


def latest_recommendation_as_of(session: Session, strategy_id: str) -> date | None:
    """Most recent ``as_of_date`` published for ``strategy_id`` (None if absent)."""

    rows = RecommendationSnapshotRepository(session).latest_snapshot(strategy_id)
    return rows[0].as_of_date if rows else None


def latest_cn_price_as_of(session: Session) -> date | None:
    """Most recent A-share ``price_snapshot`` ``obs_date`` (``.SH`` / ``.SZ``).

    The A-share daily 命门: when the refresh hangs this stops advancing. None when
    no A-share close has ever been stored."""

    return session.execute(
        select(func.max(PriceSnapshot.obs_date)).where(
            or_(
                PriceSnapshot.symbol.like("%.SH"),
                PriceSnapshot.symbol.like("%.SZ"),
            )
        )
    ).scalar_one_or_none()
