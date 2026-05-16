"""Unit tests for ``_resolve_version()``.

Covers the three-stage fallback chain documented on the function:

* RELEASE_SHA marker file present → returns its contents.
* Marker absent / blank, git available → returns the short SHA.
* Neither path works → returns ``"dev"``.

The production marker path lives at ``/srv/workbench/current/RELEASE_SHA``;
tests pass a temporary alternate path to avoid touching the live filesystem.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from workbench_api.app import _resolve_version


def test_release_sha_file_short_circuits_git_lookup(tmp_path: Path) -> None:
    marker = tmp_path / "RELEASE_SHA"
    marker.write_text("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", encoding="utf-8")
    assert _resolve_version(marker) == "a" * 40


def test_release_sha_strips_trailing_newline(tmp_path: Path) -> None:
    marker = tmp_path / "RELEASE_SHA"
    marker.write_text("deadbee\n", encoding="utf-8")
    assert _resolve_version(marker) == "deadbee"


def test_blank_marker_falls_through_to_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "RELEASE_SHA"
    marker.write_text("   \n", encoding="utf-8")

    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="abc1234\n", stderr="")

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return completed

    monkeypatch.setattr("workbench_api.app.subprocess.run", fake_run)
    assert _resolve_version(marker) == "abc1234"


def test_missing_marker_falls_through_to_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "does-not-exist"

    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="c0ffee0\n", stderr="")
    monkeypatch.setattr(
        "workbench_api.app.subprocess.run", lambda *a, **kw: completed
    )
    assert _resolve_version(marker) == "c0ffee0"


def test_returns_dev_when_marker_missing_and_git_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "no-marker"

    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git not on PATH")

    monkeypatch.setattr("workbench_api.app.subprocess.run", fake_run)
    assert _resolve_version(marker) == "dev"


def test_returns_dev_when_git_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "no-marker"
    completed = subprocess.CompletedProcess(args=[], returncode=0, stdout="\n", stderr="")
    monkeypatch.setattr(
        "workbench_api.app.subprocess.run", lambda *a, **kw: completed
    )
    assert _resolve_version(marker) == "dev"
