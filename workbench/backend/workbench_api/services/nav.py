"""NAV aggregation helper (B049 F003 — relocated from the removed dashboard service).

``aggregate_nav`` sums cash + equity across the research account rows. It was
previously ``services.dashboard._aggregate_nav``; B049 F003 removed the dead
``/api/dashboard`` route + service (the frontend had zero runtime consumers —
only OpenAPI-generated types) and relocated this genuinely-shared helper here so
``services.home`` keeps reading NAV without depending on a routeless module.

Read-only; degrades to 0.0 on DB error so the Home page renders a zeroed NAV
card rather than 500ing (B022 F014 fixing-round 2 contract).
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from workbench_api.db.models.account import Account

_logger = logging.getLogger("workbench.nav")


def aggregate_nav(session: Session) -> float:
    """Sum cash + equity_value across all accounts (single row in MVP).

    Returns 0.0 (and logs at WARNING) when the DB read raises so callers can
    still render with a zeroed NAV rather than blowing up the endpoint.
    """

    try:
        accounts = list(session.execute(select(Account)).scalars())
    except SQLAlchemyError as exc:
        _logger.warning(
            "NAV aggregation skipped due to DB error",
            extra={"event": "nav_db_error", "exception_message": str(exc)},
            exc_info=True,
        )
        session.rollback()
        return 0.0
    if not accounts:
        return 0.0
    total = 0.0
    for account in accounts:
        total += float(account.cash) + float(account.equity_value)
    return round(total, 2)
