"""B027 F002 — monthly Tiingo budget guard.

Wraps every Tiingo HTTP call so the workbench can never accidentally
blow past the $10/month Starter cap. The guard:

* reads the running month's call count from
  :class:`workbench_api.db.repositories.budget_log.BudgetLogRepository`,
* estimates dollar usage as ``calls × estimated_cost_per_call_usd``,
* raises :class:`BudgetExceeded` once the estimate hits the cap, and
* logs a structured ``tiingo_budget_near_cap`` warning at the
  ``alert_threshold_ratio`` (default 80%).

``estimated_cost_per_call_usd`` is intentionally tiny (``5e-5``) —
Tiingo Starter is a flat-rate subscription, not per-call billing, so
this number is only used to translate the call counter into a
quasi-dollar gauge against the cap. The real safety net is the call-
count check: a runaway loop that issues hundreds of thousands of
requests trips the cap long before it actually overspends.

Production wiring uses a module-level session helper so the loader
can call ``self.guard.check_and_increment()`` with no extra context.
Unit tests skip the DB by calling the inner ``_record(log)`` method
directly with a stub log; an integration test exercises the full
path against a fixture SQLite DB.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date as _date
from typing import Protocol

from sqlalchemy.orm import sessionmaker

from workbench_api.db.engine import get_engine
from workbench_api.db.repositories.budget_log import BudgetLogRepository

logger = logging.getLogger(__name__)


class _BudgetLog(Protocol):
    """Minimal contract the guard requires from the budget log surface."""

    def get_month_total_calls(self, day: _date) -> int: ...

    def increment(self, day: _date, cost_per_call_usd: float) -> None: ...


class BudgetExceeded(RuntimeError):
    """Raised by :meth:`MonthlyBudgetGuard.check_and_increment` once the
    estimated dollar usage reaches the monthly cap. Callers (the Tiingo
    loader) must let this propagate so the EOD job halts and surfaces
    the failure on ``/api/debug/recent-errors`` rather than silently
    overspending."""


@dataclass(frozen=True, slots=True)
class MonthlyBudgetGuard:
    """Stateless rate / budget gate around the Tiingo loader.

    The dataclass is frozen so a misconfiguration cannot mutate the cap
    mid-run; rotate the guard by constructing a new one if the spec
    raises the cap (B028+).
    """

    monthly_cap_usd: float = 10.0
    alert_threshold_ratio: float = 0.80
    estimated_cost_per_call_usd: float = 0.00005

    @classmethod
    def default(cls) -> MonthlyBudgetGuard:
        """Production-default values pinned to the B027 spec §4.4."""

        return cls()

    def check_and_increment(
        self,
        *,
        today: Callable[[], _date] = _date.today,
    ) -> None:
        """Production entry point — open a DB session, then delegate to
        :meth:`_record`. Tests should call :meth:`_record` directly so
        the suite stays offline.
        """

        with default_log_session() as log:
            self._record(log, today=today)

    def _record(
        self,
        log: _BudgetLog,
        *,
        today: Callable[[], _date] = _date.today,
    ) -> None:
        """Pure-data path: read counter, enforce cap, log alert, write +1.

        Split out of :meth:`check_and_increment` so unit tests can hand
        the guard a stub log without standing up a DB session.
        """

        day = today()
        calls = log.get_month_total_calls(day)
        estimated_usd = calls * self.estimated_cost_per_call_usd
        if estimated_usd >= self.monthly_cap_usd:
            raise BudgetExceeded(
                "Monthly Tiingo budget cap of "
                f"${self.monthly_cap_usd:.2f} reached "
                f"({calls} calls, estimated ${estimated_usd:.6f}). "
                "Halting backfill / EOD ingest. Verify the call volume on "
                "https://api.tiingo.com/account/usage and either wait for "
                "the next month rollover, raise the cap in "
                "workbench_api.data.cost_guard.MonthlyBudgetGuard, or "
                "rotate to the Tiingo Power tier if real growth justifies it."
            )
        if estimated_usd >= self.alert_threshold_ratio * self.monthly_cap_usd:
            logger.warning(
                "tiingo_budget_near_cap",
                extra={
                    "used_calls": calls,
                    "estimated_usd": estimated_usd,
                    "cap_usd": self.monthly_cap_usd,
                    "threshold_ratio": self.alert_threshold_ratio,
                },
            )
        log.increment(day, self.estimated_cost_per_call_usd)


@contextmanager
def default_log_session() -> Iterator[BudgetLogRepository]:
    """Open a session, yield a :class:`BudgetLogRepository`, commit on
    clean exit / rollback on exception / close in both cases.

    Module-level so tests can monkey-patch this symbol with a stub that
    yields a fake repository against a fixture DB.
    """

    factory = sessionmaker(
        bind=get_engine(), autoflush=False, autocommit=False, future=True
    )
    session = factory()
    try:
        yield BudgetLogRepository(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
