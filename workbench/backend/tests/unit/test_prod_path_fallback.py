"""B022 F014 fixing — regression for production-path fallback.

Codex F014 blockers (F009-1 + F010-1) flagged that:

* services/dashboard `_resolve_reports_dir` always anchored at the repo
  root, so production (where the docs live under
  ``/srv/workbench/current/docs/test-reports``) returned an empty list.
* services/recommendations `_resolve_runs_dir` defaulted to
  ``<repo_root>/docs/runs`` — that path doesn't exist on the VM and is
  not writable from inside the systemd unit's ReadWritePaths grant.

The fix swaps both resolvers to a prod-aware chain. These tests pin
the new behaviour so a future refactor can't silently regress to the
old single-anchor logic.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from workbench_api.services import dashboard as dashboard_service
from workbench_api.services import recommendations as recommendations_service


def test_resolve_reports_dir_prefers_repo_root_when_present(tmp_path: Path) -> None:
    """Dev path: the configured directory exists under the repo root.

    parents[4] from services/dashboard.py reaches the repo root —
    parents[3] (the prior anchor) stopped at ``workbench/`` and was
    fixed alongside the B022 F014 blocker.
    """

    del tmp_path
    repo_root = Path(dashboard_service.__file__).resolve().parents[4]
    real = repo_root / "docs" / "test-reports"
    assert real.is_dir(), f"docs/test-reports/ should exist under {repo_root}"
    resolved = dashboard_service._resolve_reports_dir("docs/test-reports")
    assert resolved == real


def test_resolve_reports_dir_falls_back_to_prod_release(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Prod path: repo-root candidate missing, fallback to /srv/workbench/current."""

    fake_release = tmp_path / "fake-current"
    (fake_release / "docs" / "test-reports").mkdir(parents=True)
    monkeypatch.setattr(dashboard_service, "PROD_RELEASE_CURRENT", fake_release)
    # Use a configured value that doesn't exist under the real repo root
    # so the prod branch fires.
    resolved = dashboard_service._resolve_reports_dir("does-not-exist-in-repo")
    # The repo-root candidate doesn't exist so the prod chain is consulted,
    # but the prod candidate ALSO needs to be present for the swap to fire.
    (fake_release / "does-not-exist-in-repo").mkdir()
    resolved = dashboard_service._resolve_reports_dir("does-not-exist-in-repo")
    assert resolved == (fake_release / "does-not-exist-in-repo")


def test_resolve_reports_dir_absolute_passthrough(tmp_path: Path) -> None:
    """Absolute paths bypass the chain entirely (operator override)."""

    resolved = dashboard_service._resolve_reports_dir(str(tmp_path))
    assert resolved == tmp_path


def test_resolve_runs_dir_uses_prod_writable_when_release_symlink_exists(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Prod marker present → use the writable /var/lib/workbench/runs constant."""

    fake_current = tmp_path / "fake-current"
    fake_current.mkdir()
    fake_runs = tmp_path / "fake-var-lib-runs"
    monkeypatch.setattr(recommendations_service, "PROD_RELEASE_CURRENT", fake_current)
    monkeypatch.setattr(recommendations_service, "PROD_RUNS_DIR", fake_runs)
    resolved = recommendations_service._resolve_runs_dir("docs/runs")
    assert resolved == fake_runs


def test_resolve_runs_dir_uses_repo_root_when_not_prod(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No prod marker → fall back to repo-root anchored path (dev)."""

    missing = tmp_path / "does-not-exist"
    monkeypatch.setattr(recommendations_service, "PROD_RELEASE_CURRENT", missing)
    resolved = recommendations_service._resolve_runs_dir("docs/runs")
    repo_root = Path(recommendations_service.__file__).resolve().parents[4]
    assert resolved == repo_root / "docs" / "runs"


def test_resolve_runs_dir_absolute_passthrough(tmp_path: Path) -> None:
    """Absolute config overrides the chain (operator-set env var)."""

    resolved = recommendations_service._resolve_runs_dir(str(tmp_path))
    assert resolved == tmp_path
