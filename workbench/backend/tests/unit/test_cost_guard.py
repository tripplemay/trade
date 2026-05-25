"""B027 F002 — MonthlyBudgetGuard unit coverage.

The tests pin the call-counter → estimated-USD → cap-or-warning ladder
without standing up a DB. A trailing test exercises the
``check_and_increment`` entry point against a fake module-level log
provider to confirm the production wiring path also fires through the
same ``_record`` codepath.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pytest

from workbench_api.data import cost_guard
from workbench_api.data.cost_guard import (
    BudgetExceeded,
    MonthlyBudgetGuard,
)


class _StubLog:
    """In-memory stand-in for :class:`BudgetLogRepository`."""

    def __init__(self, initial_calls: int = 0) -> None:
        self._calls = initial_calls
        self.increments: list[tuple[date, float]] = []

    def get_month_total_calls(self, day: date) -> int:  # noqa: ARG002
        return self._calls

    def increment(self, day: date, cost_per_call_usd: float) -> None:
        self._calls += 1
        self.increments.append((day, cost_per_call_usd))


def test_default_factory_pins_b027_spec_values() -> None:
    guard = MonthlyBudgetGuard.default()
    assert guard.monthly_cap_usd == 10.0
    assert guard.alert_threshold_ratio == 0.80
    assert guard.estimated_cost_per_call_usd == 0.00005


def test_dataclass_is_frozen_and_slots() -> None:
    """Immutable so a misconfiguration cannot mutate the cap mid-run."""

    guard = MonthlyBudgetGuard.default()
    with pytest.raises((AttributeError, TypeError)):
        guard.monthly_cap_usd = 999.0  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        guard.note = "should not stick"  # type: ignore[attr-defined]


def test_first_call_of_month_passes_silently() -> None:
    """Below the alert ratio: no warning logged, log gets +1."""

    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    log = _StubLog(initial_calls=0)
    guard = MonthlyBudgetGuard.default()
    handler = _Collector(level=logging.WARNING)
    cost_guard.logger.addHandler(handler)
    previous_level = cost_guard.logger.level
    cost_guard.logger.setLevel(logging.WARNING)
    try:
        guard._record(log, today=lambda: date(2026, 5, 26))
    finally:
        cost_guard.logger.removeHandler(handler)
        cost_guard.logger.setLevel(previous_level)
    assert log._calls == 1
    assert log.increments == [(date(2026, 5, 26), 0.00005)]
    assert records == []


def test_near_cap_logs_warning() -> None:
    """At ≥80% of the cap (without hitting it), a structured warning fires.

    We attach a list-collecting handler directly to the cost_guard logger
    so the assertion is independent of the upstream root logger's level —
    earlier tests in the suite may set logging.disable(...) or otherwise
    interfere with pytest's caplog propagation.
    """

    guard = MonthlyBudgetGuard.default()
    # 0.80 × cap / cost-per-call = 0.80 × 10 / 5e-5 = 160_000 calls.
    log = _StubLog(initial_calls=160_000)

    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Collector(level=logging.WARNING)
    cost_guard.logger.addHandler(handler)
    previous_level = cost_guard.logger.level
    cost_guard.logger.setLevel(logging.WARNING)
    try:
        guard._record(log, today=lambda: date(2026, 5, 26))
    finally:
        cost_guard.logger.removeHandler(handler)
        cost_guard.logger.setLevel(previous_level)

    near_cap = [r for r in records if r.msg == "tiingo_budget_near_cap"]
    assert near_cap, "expected tiingo_budget_near_cap warning to fire"
    record = near_cap[0]
    assert record.levelno == logging.WARNING
    extra = vars(record)
    assert extra["used_calls"] == 160_000
    assert extra["cap_usd"] == 10.0
    # Even though we logged, we still record the call so the cap math
    # doesn't get stuck just below the boundary.
    assert log._calls == 160_001


def test_at_cap_raises_budget_exceeded_without_logging_to_db() -> None:
    """≥100% of the cap raises BudgetExceeded BEFORE incrementing."""

    guard = MonthlyBudgetGuard.default()
    # 200_000 calls × 5e-5 = $10 — the cap value, ≥ check fires.
    log = _StubLog(initial_calls=200_000)
    with pytest.raises(BudgetExceeded) as exc_info:
        guard._record(log, today=lambda: date(2026, 5, 26))
    # Increment NEVER runs when the cap is hit; otherwise the audit log
    # would drift past the boundary on a tripped guard.
    assert log.increments == []
    msg = str(exc_info.value)
    assert "$10.00" in msg
    assert "Tiingo" in msg
    assert "tier" in msg or "rotate" in msg


def test_check_and_increment_routes_through_default_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The no-arg entry point used by the Tiingo loader must hit the
    same code path; we swap the session provider for a fake CM."""

    log = _StubLog(initial_calls=0)

    class _FakeSession:
        def __enter__(self) -> _StubLog:
            return log

        def __exit__(self, *_args: Any) -> None:
            return None

    monkeypatch.setattr(cost_guard, "default_log_session", lambda: _FakeSession())
    guard = MonthlyBudgetGuard.default()
    guard.check_and_increment(today=lambda: date(2026, 5, 26))
    assert log._calls == 1


def test_check_and_increment_propagates_budget_exceeded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tripped cap propagates out of the no-arg entry point so the
    loader can let it bubble up to /api/debug/recent-errors."""

    log = _StubLog(initial_calls=200_000)

    class _FakeSession:
        def __enter__(self) -> _StubLog:
            return log

        def __exit__(self, *_args: Any) -> None:
            return None

    monkeypatch.setattr(cost_guard, "default_log_session", lambda: _FakeSession())
    guard = MonthlyBudgetGuard.default()
    with pytest.raises(BudgetExceeded):
        guard.check_and_increment(today=lambda: date(2026, 5, 26))
