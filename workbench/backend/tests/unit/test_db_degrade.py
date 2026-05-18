"""B022 F014 fixing-round 2 regression — DB-error graceful degrade.

The fixing-round 2 commit added try/except + structured-log fallback
inside services/dashboard `_aggregate_nav`, services/recommendations
`_aggregate_account_state`, and services/backlog `list_backlog`.

Each fallback turns a SQLAlchemyError into a zeroed / empty response so
the corresponding page can still render its empty-state — Codex L2
caught the prior behaviour as `/api/dashboard` returning 500 with no
log entry. The app-level exception handler (in app.py) now also logs
the underlying cause; these tests pin the per-service degrade so the
pages stay responsive even if the underlying SQL fails.

We exercise the degrade by passing a fake Session whose `execute`
raises OperationalError. The downstream branch must catch + log +
return the empty state — not propagate the exception.
"""

from __future__ import annotations

import logging
from typing import Any, Never

import pytest
from sqlalchemy.exc import OperationalError

from workbench_api.services import backlog as backlog_service
from workbench_api.services import dashboard as dashboard_service
from workbench_api.services import recommendations as recommendations_service
from workbench_api.settings import Settings


class _RaisingSession:
    """Stand-in Session whose every `execute` raises OperationalError."""

    rolled_back: bool = False

    def execute(self, *_args: Any, **_kwargs: Any) -> Never:
        raise OperationalError("SELECT", {}, Exception("no such table: account"))

    def rollback(self) -> None:
        self.rolled_back = True


def test_dashboard_nav_degrades_to_zero_on_db_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="workbench.dashboard")
    session = _RaisingSession()
    result = dashboard_service._aggregate_nav(session)  # type: ignore[arg-type]
    assert result == 0.0
    assert session.rolled_back is True
    assert any("dashboard_nav_db_error" in record.message or
               "dashboard_nav_db_error" in (record.__dict__.get("event") or "")
               for record in caplog.records), caplog.records


def test_dashboard_build_completes_with_empty_nav_when_db_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The full build_dashboard path must succeed even when the DB read
    fails — it's the dashboard's whole-page render contract."""

    caplog.set_level(logging.WARNING, logger="workbench.dashboard")
    settings = Settings(WORKBENCH_REPORTS_DIR="non-existent-dir")
    response = dashboard_service.build_dashboard(_RaisingSession(), settings)  # type: ignore[arg-type]
    assert response.nav == 0.0
    assert response.master_drawdown == 0.0
    assert response.recent_reports == []
    assert response.action_items == []


def test_recommendations_account_aggregation_degrades_on_db_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="workbench.recommendations")
    session = _RaisingSession()
    present, total = recommendations_service._aggregate_account_state(session)  # type: ignore[arg-type]
    assert present is False
    assert total == 0.0
    assert session.rolled_back is True


def test_backlog_list_degrades_to_empty_on_db_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """BacklogRepository.list_all calls session.execute; the new
    try/except in list_backlog catches the SQLAlchemyError and returns
    an empty list. Mutations (POST/PATCH/DELETE) keep failing loud —
    only the read path degrades. That's an explicit policy choice
    (don't silently drop user input)."""

    caplog.set_level(logging.WARNING, logger="workbench.backlog")
    response = backlog_service.list_backlog(_RaisingSession())  # type: ignore[arg-type]
    assert response.entries == []
