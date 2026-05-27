"""B031 F002 — MonthlyBudgetGuard unit coverage.

The tests pin the USD-cumulative → projected → cap-or-warning ladder
without standing up a DB. A trailing test exercises the
``check_and_increment`` entry point against a fake module-level log
provider to confirm the production wiring path also fires through
the same ``_record`` codepath.

Shape mirrors :mod:`tests.unit.test_cost_guard` (Tiingo B027) but
asserts on USD totals — LLM cost is per-request variable, so the
guard tracks dollars instead of call counts (which Tiingo's
flat-rate subscription justified).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pytest

from workbench_api.llm import cost_guard
from workbench_api.llm.cost_guard import (
    USD_TO_CNY_RATE,
    BudgetExceeded,
    MonthlyBudgetGuard,
)


class _StubLog:
    """In-memory stand-in for :class:`LLMBudgetLogRepository`.

    Tracks the per-month running total + every increment so tests can
    assert on the exact sequence of writes the guard issued.
    """

    def __init__(self, initial_usd: float = 0.0) -> None:
        self._usd = initial_usd
        self.increments: list[tuple[date, float]] = []

    def get_month_total_usd(self, day: date) -> float:  # noqa: ARG002 — month-aware stub
        return self._usd

    def increment(self, day: date, cost_usd: float) -> None:
        self._usd += cost_usd
        self.increments.append((day, cost_usd))


def test_default_factory_pins_b031_spec_values() -> None:
    """Production defaults must match spec §4.4 — a forgotten kwarg
    on a future caller cannot silently widen the cap."""

    guard = MonthlyBudgetGuard.default()
    assert guard.monthly_cap_usd == 200.0
    assert guard.alert_threshold_ratio == 0.80


def test_dataclass_is_frozen_and_slots() -> None:
    """Immutable so a misconfiguration cannot mutate the cap mid-run."""

    guard = MonthlyBudgetGuard.default()
    with pytest.raises((AttributeError, TypeError)):
        guard.monthly_cap_usd = 9999.0  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        guard.note = "should not stick"  # type: ignore[attr-defined]


def test_first_call_of_month_passes_silently() -> None:
    """Below the alert ratio: no warning logged, log gets +cost."""

    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    log = _StubLog(initial_usd=0.0)
    guard = MonthlyBudgetGuard.default()
    handler = _Collector(level=logging.WARNING)
    cost_guard.logger.addHandler(handler)
    previous_level = cost_guard.logger.level
    cost_guard.logger.setLevel(logging.WARNING)
    try:
        guard._record(log, estimated_cost_usd=10.0, today=lambda: date(2026, 5, 27))
    finally:
        cost_guard.logger.removeHandler(handler)
        cost_guard.logger.setLevel(previous_level)
    assert log.increments == [(date(2026, 5, 27), 10.0)]
    assert records == []


def test_near_cap_logs_warning() -> None:
    """At ≥80% of the cap (without hitting it), a structured warning
    fires so the caller can switch to a fallback model BEFORE the
    hard halt."""

    guard = MonthlyBudgetGuard.default()
    # cap=200 USD * 0.80 = 160 USD threshold. Pre-load 155 USD; the
    # next 10 USD call projects to 165 which is ≥ 160 but < 200.
    log = _StubLog(initial_usd=155.0)

    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Collector(level=logging.WARNING)
    cost_guard.logger.addHandler(handler)
    previous_level = cost_guard.logger.level
    cost_guard.logger.setLevel(logging.WARNING)
    try:
        guard._record(log, estimated_cost_usd=10.0, today=lambda: date(2026, 5, 27))
    finally:
        cost_guard.logger.removeHandler(handler)
        cost_guard.logger.setLevel(previous_level)
    assert len(records) == 1
    assert records[0].message == "llm_budget_near_cap"
    fields: dict[str, Any] = vars(records[0])
    assert fields.get("projected_usd") == pytest.approx(165.0)
    assert fields.get("cap_usd") == 200.0
    # Log still got the +10 since alert is non-blocking.
    assert log.increments == [(date(2026, 5, 27), 10.0)]


def test_cap_hit_raises_budget_exceeded() -> None:
    """≥100% of the cap raises BudgetExceeded BEFORE writing the
    increment — the cap is a hard halt, not a warning."""

    guard = MonthlyBudgetGuard.default()
    log = _StubLog(initial_usd=199.5)
    with pytest.raises(BudgetExceeded) as exc_info:
        guard._record(log, estimated_cost_usd=1.0, today=lambda: date(2026, 5, 27))
    message = str(exc_info.value)
    assert "$200.00" in message
    assert "Monthly LLM budget cap" in message
    # Per spec the exception must include the ¥-equivalent — operators
    # reading a Chinese-language alert console should see the product
    # spec's currency, not just USD.
    assert "¥1500" in message
    assert "_fallback" in message  # remediation pointer mentions the fallback chain
    # The increment must NOT have landed — cap raises before write.
    assert log.increments == []


def test_budget_exceeded_message_uses_usd_to_cny_rate() -> None:
    """The exchange rate constant feeds the human-readable message;
    a non-default cap recomputes ¥-equivalent on the fly."""

    guard = MonthlyBudgetGuard(monthly_cap_usd=100.0, alert_threshold_ratio=0.80)
    log = _StubLog(initial_usd=99.5)
    with pytest.raises(BudgetExceeded) as exc_info:
        guard._record(log, estimated_cost_usd=1.0, today=lambda: date(2026, 5, 27))
    expected_cny = int(100.0 * USD_TO_CNY_RATE)
    assert f"¥{expected_cny}" in str(exc_info.value)


def test_check_and_increment_uses_module_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The production entry point opens a session via
    ``default_log_session``. Monkey-patching that symbol must
    intercept the path without standing up a real DB.

    Spec §F002 (5): /api/debug/recent-errors should be able to
    surface the warning + BudgetExceeded; that hook only fires if
    the production path runs through ``check_and_increment``, so we
    pin the routing here.
    """

    captured: list[float] = []

    class _FakeLog:
        def get_month_total_usd(self, day: date) -> float:  # noqa: ARG002
            return 0.0

        def increment(self, day: date, cost_usd: float) -> None:  # noqa: ARG002
            captured.append(cost_usd)

    from contextlib import contextmanager

    @contextmanager
    def _fake_session():  # type: ignore[no-untyped-def]
        yield _FakeLog()

    monkeypatch.setattr(cost_guard, "default_log_session", _fake_session)
    guard = MonthlyBudgetGuard.default()
    guard.check_and_increment(estimated_cost_usd=2.5, today=lambda: date(2026, 5, 27))
    assert captured == [2.5]


def test_alert_threshold_excludes_below_eighty_percent() -> None:
    """Just under the alert ratio must NOT log a warning. Pin the
    boundary so a future refactor of the comparison operator
    surfaces here."""

    guard = MonthlyBudgetGuard.default()
    # Projected total = 159.99 USD < 0.80 * 200 = 160.
    log = _StubLog(initial_usd=149.99)

    records: list[logging.LogRecord] = []

    class _Collector(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Collector(level=logging.WARNING)
    cost_guard.logger.addHandler(handler)
    previous_level = cost_guard.logger.level
    cost_guard.logger.setLevel(logging.WARNING)
    try:
        guard._record(log, estimated_cost_usd=10.0, today=lambda: date(2026, 5, 27))
    finally:
        cost_guard.logger.removeHandler(handler)
        cost_guard.logger.setLevel(previous_level)
    assert records == []
