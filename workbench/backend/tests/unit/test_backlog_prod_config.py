"""B022 F014 fixing-round 3 regression — backlog config prod fallback.

The production VM runs the backend from a wheel install under
``/srv/workbench/.../site-packages``; ``Path(__file__).parents[4]``
in ``routes/backlog._default_config`` resolves somewhere unrelated to
any git working tree, so the dev-time ``backlog.json`` + ``git add``
+ ``git commit`` chain blew up on every backlog mutation in prod.
Round-3 makes the config prod-aware: when ``/srv/workbench/current``
exists, write to ``/var/lib/workbench/backlog/backlog.json`` and skip
the git step via ``_noop_git_runner``.

These tests pin both branches without actually touching the prod
paths — we monkeypatch the marker constant ``PROD_RELEASE_CURRENT``
to point at a tmp dir, plus override ``PROD_BACKLOG_DIR`` so the
mkdir lands in a writable test location.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from workbench_api.routes import backlog as backlog_route


def test_default_config_uses_prod_paths_when_release_symlink_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When /srv/workbench/current exists (prod marker), the config
    points at /var/lib/workbench/backlog/backlog.json and uses the
    no-op git_runner."""

    fake_release = tmp_path / "srv-current"
    fake_release.mkdir()
    fake_backlog_dir = tmp_path / "var-workbench-backlog"

    monkeypatch.setattr(backlog_route, "PROD_RELEASE_CURRENT", fake_release)
    monkeypatch.setattr(backlog_route, "PROD_BACKLOG_DIR", fake_backlog_dir)

    config = backlog_route._default_config()

    assert config.repo_root == fake_backlog_dir
    assert config.backlog_file == fake_backlog_dir / "backlog.json"
    assert config.git_runner is backlog_route._noop_git_runner
    # The prod branch must mkdir on demand so a fresh VM doesn't need
    # any pre-deploy setup beyond the systemd ReadWritePaths grant.
    assert fake_backlog_dir.exists() and fake_backlog_dir.is_dir()


def test_default_config_uses_dev_paths_when_no_release_symlink(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In dev (no /srv/workbench/current), repo_root is parents[4]
    and git_runner is the real subprocess runner."""

    fake_release = tmp_path / "srv-current"
    # Intentionally NOT mkdir; the marker must be absent.
    monkeypatch.setattr(backlog_route, "PROD_RELEASE_CURRENT", fake_release)

    config = backlog_route._default_config()

    # Anchored at the real repo root (the test runs from the repo).
    # parents[4] of routes/backlog.py is the repo root.
    expected_repo_root = Path(
        backlog_route.__file__
    ).resolve().parents[4]
    assert config.repo_root == expected_repo_root
    assert config.backlog_file == expected_repo_root / "backlog.json"

    from workbench_api.services.backlog import _real_git_runner

    assert config.git_runner is _real_git_runner


def test_noop_git_runner_logs_and_does_nothing(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """_noop_git_runner must log the skip event with the git args and
    return without raising — the prod path persists JSON only."""

    caplog.set_level(logging.INFO, logger="workbench.backlog")
    backlog_route._noop_git_runner(
        ["git", "commit", "-m", "chore(backlog): add BL-WB-FAKE"],
        tmp_path,
    )
    assert any(
        record.__dict__.get("event") == "backlog_git_skipped_prod"
        for record in caplog.records
    ), caplog.records
