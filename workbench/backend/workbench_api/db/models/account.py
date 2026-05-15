"""Account model — mirrors B012's research-account state.

Single-user workbench keeps a single row most of the time; the primary key
remains ``account_id`` so a future multi-account research workspace
(non-MVP) can extend without a schema migration. Cash + equity track the
mock-broker account state defined in B012; ``as_of_date`` is the journal
timestamp the user enters when re-importing.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from workbench_api.db.models.base import Base


class Account(Base):
    __tablename__ = "account"

    account_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(8), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    equity_value: Mapped[float] = mapped_column(Numeric(20, 4), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)

    def __repr__(self) -> str:
        return f"Account(account_id={self.account_id!r}, name={self.name!r})"
