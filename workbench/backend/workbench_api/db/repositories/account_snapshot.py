"""AccountSnapshotRepository — point-in-time account state (B023 F001).

Beyond the generic 5-method surface, exposes:

* ``latest()`` — most recent snapshot by ``snapshot_at``. The
  Recommendations page, the Position-diff page (F002), and the reconcile
  route (F005) all read through this so they see the same canonical
  state without having to sort the full table.
"""

from __future__ import annotations

from sqlalchemy import select

from workbench_api.db.models.account_snapshot import AccountSnapshot
from workbench_api.db.repositories.base import Repository


class AccountSnapshotRepository(Repository[AccountSnapshot, str]):
    model = AccountSnapshot
    primary_key_attr = "id"

    def latest(self) -> AccountSnapshot | None:
        stmt = select(AccountSnapshot).order_by(AccountSnapshot.snapshot_at.desc()).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()
