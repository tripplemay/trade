"""Repository layer — thin SQLAlchemy wrappers, zero business logic.

Each repository exposes the same five-method surface (``get_by_id``,
``list_all``, ``upsert``, ``delete``, ``count``) so route handlers and the
bootstrap CLI can swap models without learning new ergonomics.
"""

from workbench_api.db.repositories.account import AccountRepository
from workbench_api.db.repositories.backlog import BacklogRepository
from workbench_api.db.repositories.base import Repository
from workbench_api.db.repositories.snapshot import SnapshotMetaRepository

__all__ = [
    "AccountRepository",
    "BacklogRepository",
    "Repository",
    "SnapshotMetaRepository",
]
