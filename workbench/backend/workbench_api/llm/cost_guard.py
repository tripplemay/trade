"""B031 F002 — monthly LLM budget guard.

Wraps every aigc-gateway HTTP call so the workbench can never
accidentally blow past the **¥1500 / $200** monthly cap per
``docs/product/llm-provider-evaluation-2026-05.md`` §6. The guard:

* reads the running month's USD total from
  :class:`workbench_api.db.repositories.llm_budget_log.LLMBudgetLogRepository`,
* adds the per-request dollar estimate the caller supplies (from
  :func:`workbench_api.llm.routing.estimate_cost_usd`),
* raises :class:`BudgetExceeded` once the projected total hits the cap, and
* logs a structured ``llm_budget_near_cap`` warning at the
  ``alert_threshold_ratio`` (default 80%).

Permanent boundary **(m)** ties spend to this guard — every advise /
embed call invokes ``check_and_increment`` BEFORE issuing the HTTP
request so a runaway loop or a mis-routed expensive model trips the
cap before billing reality.

Shape mirrors :class:`workbench_api.data.cost_guard.MonthlyBudgetGuard`
(Tiingo B027) but tracks **USD per call** instead of call counts —
LLM cost varies by model + token mix, so a flat cost-per-call
estimate would either over-protect Haiku or under-protect Opus.

Production wiring uses a module-level session helper so the
gateway can call ``self.guard.check_and_increment(estimated_cost_usd=...)``
with no extra context. Unit tests skip the DB by calling the inner
``_record(log)`` method directly with a stub log; an integration
test exercises the full path against a fixture SQLite DB.
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
from workbench_api.db.repositories.llm_budget_log import LLMBudgetLogRepository

logger = logging.getLogger(__name__)


# ¥1500 ≈ $200 USD (按 2026-05-26 中间汇率 7.5).
# Spec docs/product/llm-provider-evaluation-2026-05.md §6 pins the
# ¥1500 figure; the USD-equivalent is recomputed here so the SQLite
# log + estimate_cost_usd both stay in dollars.
USD_TO_CNY_RATE: float = 7.5
"""Reference exchange rate for the BudgetExceeded message. Not used
in any arithmetic — only when humans read the error message."""


class _BudgetLog(Protocol):
    """Minimal contract the guard requires from the budget log surface."""

    def get_month_total_usd(self, day: _date) -> float: ...

    def increment(self, day: _date, cost_usd: float) -> None: ...


class BudgetExceeded(RuntimeError):
    """Raised by :meth:`MonthlyBudgetGuard.check_and_increment` once
    the projected dollar usage hits the monthly cap. Callers (the
    :class:`workbench_api.llm.gateway.LLMGateway`) must let this
    propagate so the request layer halts — surfacing the failure on
    ``/api/debug/recent-errors`` is preferable to silently
    overspending.

    The exception message includes the ¥-equivalent so a human reading
    the error log on a Chinese-language operator console sees the cap
    in the currency the product spec quoted."""


@dataclass(frozen=True, slots=True)
class MonthlyBudgetGuard:
    """Stateless USD-budget gate around the aigc-gateway.

    The dataclass is frozen so a misconfiguration cannot mutate the
    cap mid-run; rotate the guard by constructing a new one if the
    spec raises the cap.
    """

    monthly_cap_usd: float = 200.0
    """≈ ¥1500 at USD_TO_CNY_RATE = 7.5. Spec §6 pin."""

    alert_threshold_ratio: float = 0.80
    """At ≥80% of the cap, log ``llm_budget_near_cap`` so the operator
    can switch to a fallback model BEFORE the hard halt."""

    @classmethod
    def default(cls) -> MonthlyBudgetGuard:
        """Production-default values pinned to the B031 spec §4.4."""

        return cls()

    def check_and_increment(
        self,
        *,
        estimated_cost_usd: float,
        today: Callable[[], _date] = _date.today,
    ) -> None:
        """Production entry point — open a DB session, then delegate
        to :meth:`_record`. Tests should call :meth:`_record` directly
        so the suite stays offline.

        ``estimated_cost_usd`` is the caller's pre-computed dollar
        estimate (see :func:`workbench_api.llm.routing.estimate_cost_usd`).
        Pass 0 if the call should be observed but not budget-checked
        — e.g. a free-tier embedding lookup — though the simpler
        path is for the caller to skip the guard entirely.
        """

        with default_log_session() as log:
            self._record(log, estimated_cost_usd=estimated_cost_usd, today=today)

    def _record(
        self,
        log: _BudgetLog,
        *,
        estimated_cost_usd: float,
        today: Callable[[], _date] = _date.today,
    ) -> None:
        """Pure-data path: read total, project, enforce cap, alert, write.

        Split out of :meth:`check_and_increment` so unit tests can
        hand the guard a stub log without standing up a DB session.
        """

        day = today()
        current_usd = log.get_month_total_usd(day)
        projected_usd = current_usd + estimated_cost_usd
        if projected_usd >= self.monthly_cap_usd:
            raise BudgetExceeded(
                "Monthly LLM budget cap of "
                f"${self.monthly_cap_usd:.2f} "
                f"(¥{self.monthly_cap_usd * USD_TO_CNY_RATE:.0f}) reached "
                f"(used ${current_usd:.6f}, this call estimated "
                f"${estimated_cost_usd:.6f}). Halting aigc-gateway request. "
                "Switch the caller to a fallback task "
                "(_fallback_advisor / _fallback_news / _fallback_embedding "
                "in workbench_api.llm.routing.ROUTING_TABLE) until next "
                "month, raise the cap in "
                "workbench_api.llm.cost_guard.MonthlyBudgetGuard if "
                "real usage justifies it, or wait for the next month "
                "rollover."
            )
        if projected_usd >= self.alert_threshold_ratio * self.monthly_cap_usd:
            logger.warning(
                "llm_budget_near_cap",
                extra={
                    "used_usd": current_usd,
                    "projected_usd": projected_usd,
                    "estimated_cost_usd": estimated_cost_usd,
                    "cap_usd": self.monthly_cap_usd,
                    "threshold_ratio": self.alert_threshold_ratio,
                },
            )
        log.increment(day, estimated_cost_usd)


@contextmanager
def default_log_session() -> Iterator[LLMBudgetLogRepository]:
    """Open a session, yield an :class:`LLMBudgetLogRepository`,
    commit on clean exit / rollback on exception / close in both
    cases.

    Module-level so tests can monkey-patch this symbol with a stub
    that yields a fake repository against a fixture DB.
    """

    factory = sessionmaker(
        bind=get_engine(), autoflush=False, autocommit=False, future=True
    )
    session = factory()
    try:
        yield LLMBudgetLogRepository(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
