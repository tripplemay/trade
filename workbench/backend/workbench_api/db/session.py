"""Per-request SQLAlchemy session wiring."""

from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from workbench_api.db.engine import get_engine


def _make_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a Session per-request.

    Commits on a clean exit, rolls back on exception, closes either way.
    Routes consume it through the ``SessionDep`` alias below.
    """

    factory = _make_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SessionDep = Annotated[Session, Depends(get_session)]
