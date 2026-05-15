"""``workbench-bootstrap`` happy-path + idempotency coverage."""

from __future__ import annotations

import contextlib
import json
from decimal import Decimal
from pathlib import Path

from workbench_api.cli.bootstrap import run
from workbench_api.db.repositories import AccountRepository, BacklogRepository
from workbench_api.db.session import get_session


def _seed_repo_root(repo_root: Path) -> None:
    (repo_root / "accounts").mkdir(parents=True, exist_ok=True)
    (repo_root / "accounts" / "me.json").write_text(
        json.dumps(
            {
                "account_id": "research-mvp",
                "name": "Research MVP",
                "base_currency": "USD",
                "cash": "250000",
                "equity_value": "0",
                "as_of_date": "2026-05-15",
            }
        )
    )
    (repo_root / "backlog.json").write_text(
        json.dumps(
            [
                {
                    "id": "BL-X-1",
                    "title": "Task one",
                    "description": "First seed",
                    "priority": "low",
                    "decisions": ["d1"],
                    "confirmed_at": "2026-05-15",
                    "source": "unit-test",
                },
                {
                    "id": "BL-X-2",
                    "title": "Task two",
                    "description": "Second seed",
                    "priority": "high",
                    "decisions": [],
                    "confirmed_at": "2026-05-15",
                },
            ]
        )
    )


def test_bootstrap_imports_repo_root_files(initialised_db: str, tmp_path: Path) -> None:
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
    _seed_repo_root(repo_root)

    counts = run(repo_root)
    assert counts == {"accounts": 1, "backlog": 2}

    gen = get_session()
    session = next(gen)
    account = AccountRepository(session).get_by_id("research-mvp")
    assert account is not None
    assert account.cash == Decimal("250000")
    backlog = {row.id: row for row in BacklogRepository(session).list_all()}
    assert set(backlog) == {"BL-X-1", "BL-X-2"}
    assert backlog["BL-X-2"].priority == "high"
    with contextlib.suppress(StopIteration):
        next(gen)


def test_bootstrap_is_idempotent(initialised_db: str, tmp_path: Path) -> None:
    repo_root = tmp_path / "fake-repo"
    repo_root.mkdir()
    _seed_repo_root(repo_root)

    run(repo_root)
    counts = run(repo_root)
    assert counts == {"accounts": 1, "backlog": 2}

    gen = get_session()
    session = next(gen)
    assert AccountRepository(session).count() == 1
    assert BacklogRepository(session).count() == 2
    with contextlib.suppress(StopIteration):
        next(gen)


def test_bootstrap_handles_missing_files(initialised_db: str, tmp_path: Path) -> None:
    """A fresh clone may have no accounts/me.json and no backlog.json; the
    CLI must succeed with zero imports rather than crashing.
    """

    repo_root = tmp_path / "empty-repo"
    repo_root.mkdir()
    counts = run(repo_root)
    assert counts == {"accounts": 0, "backlog": 0}
