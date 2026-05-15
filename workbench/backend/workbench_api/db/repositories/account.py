"""AccountRepository — single-row research-account state."""

from __future__ import annotations

from workbench_api.db.models.account import Account
from workbench_api.db.repositories.base import Repository


class AccountRepository(Repository[Account, str]):
    model = Account
    primary_key_attr = "account_id"
