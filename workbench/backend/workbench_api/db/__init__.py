"""Workbench persistence layer.

SQLite + SQLAlchemy 2.x + Alembic. The workbench is single-VM, single-user,
so a single SQLite file at ``/var/lib/workbench/db/workbench.db`` (prod) or
``./workbench-dev.db`` (dev) is sufficient. B021's `Out of Scope` section
explicitly rules out Postgres / MySQL / managed cloud SQL.
"""

from workbench_api.db.engine import get_engine
from workbench_api.db.models.base import Base
from workbench_api.db.session import SessionDep, get_session

__all__ = ["Base", "SessionDep", "get_engine", "get_session"]
