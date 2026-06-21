"""DB fixtures for the B071 F004 backend acceptance tier.

Self-contained copies of ``tmp_db_url`` / ``initialised_db`` (mirroring
``tests/unit/conftest.py``) so the acceptance suite — run as its own CI step
(``pytest tests/acceptance``) — can stand up a fresh SQLite schema without
depending on the unit conftest's directory scope.
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
    db_path = tmp_path / "workbench-acceptance.db"
    url = f"sqlite:///{db_path}"
    monkeypatch.setenv("WORKBENCH_DB_URL", url)
    reset_engine()
    get_settings()
    yield url
    reset_engine()


@pytest.fixture
def initialised_db(tmp_db_url: str) -> Iterator[str]:
    engine = get_engine()
    Base.metadata.create_all(engine)
    yield tmp_db_url
    Base.metadata.drop_all(engine)
