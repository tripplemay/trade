"""Shared fixtures for the workbench backend test suite.

The DB tests run against a per-test SQLite file in pytest's ``tmp_path`` so
they don't trample on the dev DB and can run in parallel. ``WORKBENCH_DB_URL``
is set before the engine is created so settings + engine + sessionmaker
all point at the same fixture file.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from workbench_api.db.engine import get_engine, reset_engine
from workbench_api.db.models import Base
from workbench_api.settings import get_settings


@pytest.fixture
def tmp_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Point the workbench at a fresh SQLite file for the test."""

    db_path = tmp_path / "workbench-test.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("WORKBENCH_DB_URL", url)
    # `get_settings` is not memoized; the engine is. Reset both so the new
    # URL takes effect on first access.
    reset_engine()
    get_settings()
    yield url
    reset_engine()


@pytest.fixture
def initialised_db(tmp_db_url: str) -> Iterator[str]:
    """Create the workbench schema directly from the ORM metadata.

    Tests that need the live DB schema use this fixture; tests that exercise
    Alembic itself use ``tmp_db_url`` and drive the migrate script.
    """

    engine = get_engine()
    Base.metadata.create_all(engine)
    yield tmp_db_url
    Base.metadata.drop_all(engine)
