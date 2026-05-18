"""OrderTicketRepository — ticket records produced by B023 F003.

Beyond the generic 5-method surface, exposes:

* ``latest()`` — most recently created ticket (Recommendations page header).
* ``reconcile(ticket_id, executed_at)`` — flip ``status`` from
  ``generated`` to ``executed`` and stamp ``executed_at``. Returns the
  updated row or ``None`` if the ticket does not exist or is not in the
  ``generated`` state. Idempotent: re-running on an already-executed
  ticket is a no-op so the F005 reconcile route can be retried without
  duplicating snapshots.
* ``void(ticket_id)`` — flip status to ``voided`` for tickets the user
  decided not to trade.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from workbench_api.db.models.order_ticket import OrderTicket
from workbench_api.db.repositories.base import Repository


class OrderTicketRepository(Repository[OrderTicket, str]):
    model = OrderTicket
    primary_key_attr = "id"

    def latest(self) -> OrderTicket | None:
        stmt = select(OrderTicket).order_by(OrderTicket.created_at.desc()).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()

    def reconcile(self, ticket_id: str, executed_at: datetime) -> OrderTicket | None:
        ticket = self.get_by_id(ticket_id)
        if ticket is None:
            return None
        if ticket.status == "executed":
            return ticket
        if ticket.status != "generated":
            return None
        ticket.status = "executed"
        ticket.executed_at = executed_at
        self._session.flush()
        return ticket

    def void(self, ticket_id: str) -> OrderTicket | None:
        ticket = self.get_by_id(ticket_id)
        if ticket is None:
            return None
        if ticket.status == "voided":
            return ticket
        if ticket.status != "generated":
            return None
        ticket.status = "voided"
        self._session.flush()
        return ticket
