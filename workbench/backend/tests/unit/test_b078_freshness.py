"""B078 F002 — pure data-freshness verdicts (business-day age + stuck service).

Deterministic anchors (no DB, no real-calendar dependence): 2024-01-05 is a
Friday, 2024-01-08 a Monday, so the Friday→Monday gap is exactly one business
day (a weekend never ages a snapshot past a one-day check).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from workbench_api.data_refresh.freshness import (
    DEFAULT_MAX_SNAPSHOT_AGE_BUSINESS_DAYS,
    assess_as_of_freshness,
    assess_service_activating,
    business_days_between,
)

_FRI = date(2024, 1, 5)
_MON = date(2024, 1, 8)
_FRI_NEXT = date(2024, 1, 12)


def test_business_days_skip_the_weekend() -> None:
    assert business_days_between(_FRI, _MON) == 1  # only Monday counts
    assert business_days_between(_MON, _FRI_NEXT) == 4  # Tue..Fri
    assert business_days_between(_FRI, _FRI_NEXT) == 5  # Mon..Fri


def test_business_days_same_or_future_is_zero() -> None:
    assert business_days_between(_MON, _MON) == 0
    assert business_days_between(_FRI_NEXT, _FRI) == 0  # end before start


def test_fresh_snapshot_within_threshold() -> None:
    v = assess_as_of_freshness("reco", _FRI, _MON, max_business_days=3)
    assert v.is_fresh is True
    assert v.age_business_days == 1


def test_stale_snapshot_beyond_threshold_is_caught() -> None:
    # _FRI → _FRI_NEXT = 5 business days > 3 → STALE (the B078 silent freeze).
    v = assess_as_of_freshness("reco", _FRI, _FRI_NEXT, max_business_days=3)
    assert v.is_fresh is False
    assert v.age_business_days == 5
    assert "STALE" in v.reason


def test_missing_as_of_is_not_fresh() -> None:
    v = assess_as_of_freshness("price", None, _MON)
    assert v.is_fresh is False
    assert v.age_business_days is None


def test_default_threshold_catches_the_exact_b078_freeze() -> None:
    # The real B078 freeze: A-share data frozen Mon 2026-06-22, discovered Fri
    # 2026-06-26 = 4 business days. This MUST be STALE with the SHIPPED DEFAULT (no
    # max_business_days kwarg → uses the constant). Pins the default so a one-line
    # regression of DEFAULT_MAX_SNAPSHOT_AGE_BUSINESS_DAYS (3→4) — which would
    # silently re-open B078 — turns this test red.
    assert DEFAULT_MAX_SNAPSHOT_AGE_BUSINESS_DAYS <= 3
    frozen = date(2026, 6, 22)  # Monday
    discovered = date(2026, 6, 26)  # Friday
    v = assess_as_of_freshness("cn_price", frozen, discovered)
    assert v.age_business_days == 4
    assert v.is_fresh is False


def test_service_active_is_not_stuck() -> None:
    now = datetime(2024, 1, 8, 12, 0, tzinfo=UTC)
    assert assess_service_activating("active", None, now).is_stuck is False
    assert assess_service_activating("inactive", None, now).is_stuck is False


def test_service_activating_briefly_is_not_stuck() -> None:
    now = datetime(2024, 1, 8, 12, 0, tzinfo=UTC)
    since = now - timedelta(minutes=10)
    assert assess_service_activating("activating", since, now).is_stuck is False


def test_service_stuck_activating_for_days_is_caught() -> None:
    # The B078 state: activating for 3 days → STUCK.
    now = datetime(2024, 1, 8, 12, 0, tzinfo=UTC)
    since = now - timedelta(days=3)
    v = assess_service_activating("activating", since, now)
    assert v.is_stuck is True
    assert "STUCK" in v.reason


def test_service_activating_unknown_since_is_not_flagged() -> None:
    now = datetime(2024, 1, 8, 12, 0, tzinfo=UTC)
    assert assess_service_activating("activating", None, now).is_stuck is False
