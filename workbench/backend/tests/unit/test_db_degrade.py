"""B022 F014 fixing-round 2 regression — DB-error graceful degrade.

The fixing-round 2 commit added try/except + structured-log fallback
inside services/nav `aggregate_nav` (B049 F003: relocated from the removed
services/dashboard `_aggregate_nav`), services/recommendations
`_aggregate_account_state`, and services/backlog `list_backlog`.

Each fallback turns a SQLAlchemyError into a zeroed / empty response so
the corresponding page can still render its empty-state. The app-level
exception handler (in app.py) now also logs the underlying cause; these
tests pin the per-service degrade so the pages stay responsive even if the
underlying SQL fails.

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
from workbench_api.services import nav as nav_service
from workbench_api.services import recommendations as recommendations_service
from workbench_api.services import snapshots as snapshots_service


class _RaisingSession:
    """Stand-in Session whose every `execute` raises OperationalError."""

    rolled_back: bool = False

    def execute(self, *_args: Any, **_kwargs: Any) -> Never:
        raise OperationalError("SELECT", {}, Exception("no such table: account"))

    def rollback(self) -> None:
        self.rolled_back = True


def test_nav_degrades_to_zero_on_db_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="workbench.nav")
    session = _RaisingSession()
    result = nav_service.aggregate_nav(session)  # type: ignore[arg-type]
    assert result == 0.0
    assert session.rolled_back is True
    assert any("nav_db_error" in record.message or
               "nav_db_error" in (record.__dict__.get("event") or "")
               for record in caplog.records), caplog.records


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


def test_snapshots_list_degrades_to_empty_on_db_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """B022 F014 fixing-round 3: SnapshotMetaRepository.list_all
    raises OperationalError → list_snapshots logs + rolls back +
    returns an empty SnapshotListResponse so the /snapshots page
    renders its empty state instead of 500ing."""

    caplog.set_level(logging.WARNING, logger="workbench.snapshots")
    session = _RaisingSession()
    response = snapshots_service.list_snapshots(session)  # type: ignore[arg-type]
    assert response.snapshots == []
    assert session.rolled_back is True
    assert any(
        "snapshots_list_db_error" in record.message
        or "snapshots_list_db_error" in (record.__dict__.get("event") or "")
        for record in caplog.records
    ), caplog.records
