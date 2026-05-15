"""Generic Repository — shared CRUD surface for the workbench's ORM tables.

The class is intentionally minimal: every method maps to a single
SQLAlchemy 2.x call. Anything that needs to grow into a multi-step query
should live on the route handler that owns it, not here.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar, cast

from sqlalchemy import select
from sqlalchemy.orm import InstrumentedAttribute, Session

from workbench_api.db.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)
KeyT = TypeVar("KeyT")


class Repository(Generic[ModelT, KeyT]):
    """Lookup + CRUD operations against a single ORM model.

    Subclasses supply ``model`` and ``primary_key_attr``; everything else
    is shared.
    """

    model: type[ModelT]
    primary_key_attr: str

    def __init__(self, session: Session) -> None:
        self._session = session

    def _pk_column(self) -> InstrumentedAttribute[Any]:
        return cast(InstrumentedAttribute[Any], getattr(self.model, self.primary_key_attr))

    def get_by_id(self, key: KeyT) -> ModelT | None:
        stmt = select(self.model).where(self._pk_column() == key)
        return self._session.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[ModelT]:
        stmt = select(self.model).order_by(self._pk_column())
        return list(self._session.execute(stmt).scalars().all())

    def upsert(self, instance: ModelT) -> ModelT:
        """Insert if absent, otherwise update field-by-field.

        ``session.merge`` would do this in one call, but we want field
        assignment to be transparent (debuggable in pytest) and to honour
        ``Mapped[Type]`` defaults defined on the model.
        """

        pk_value = getattr(instance, self.primary_key_attr)
        existing = self.get_by_id(pk_value)
        if existing is None:
            self._session.add(instance)
            self._session.flush()
            return instance
        for column in self.model.__table__.columns:
            name = column.name
            if name == self.primary_key_attr:
                continue
            setattr(existing, name, getattr(instance, name))
        self._session.flush()
        return existing

    def delete(self, key: KeyT) -> bool:
        existing = self.get_by_id(key)
        if existing is None:
            return False
        self._session.delete(existing)
        self._session.flush()
        return True

    def count(self) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(self.model)
        return int(self._session.execute(stmt).scalar_one())
