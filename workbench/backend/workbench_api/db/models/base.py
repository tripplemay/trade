"""Declarative base class shared by every workbench ORM model.

Subclasses use SQLAlchemy 2.x's typed ``Mapped[...]`` / ``mapped_column``
pattern so mypy strict mode can verify the model surface without a plugin.
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """All workbench ORM tables inherit from this base."""
