"""Smoke coverage for the workbench DB engine + session factory."""

from __future__ import annotations

import contextlib

from sqlalchemy import text

from workbench_api.db.engine import get_engine, reset_engine
from workbench_api.db.session import get_session


def test_engine_picks_up_env_var_after_reset(tmp_db_url: str) -> None:
    engine = get_engine()
    assert tmp_db_url.endswith(".db")
    assert engine.url.database is not None and engine.url.database.endswith("workbench-test.db")


def test_get_session_commits_on_success(initialised_db: str) -> None:
    gen = get_session()
    session = next(gen)
    session.execute(text("CREATE TABLE smoke_marker (id INTEGER PRIMARY KEY)"))
    session.execute(text("INSERT INTO smoke_marker (id) VALUES (1)"))
    # Closing the generator triggers the commit branch.
    with contextlib.suppress(StopIteration):
        next(gen)

    # A second session in the same engine still sees the row → commit ran.
    gen2 = get_session()
    session2 = next(gen2)
    row = session2.execute(text("SELECT id FROM smoke_marker")).scalar_one()
    assert row == 1
    with contextlib.suppress(StopIteration):
        next(gen2)


def test_reset_engine_drops_cache(tmp_db_url: str) -> None:
    first = get_engine()
    reset_engine()
    second = get_engine()
    assert first is not second
