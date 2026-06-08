"""B047-OPS1 F001 — env hard-fail guard for the write-CLI entrypoints.

These tests pin the B047 re-verify root cause shut: a bare
``python -m workbench_api.backtests.{canonical,worker}`` with no
``WORKBENCH_DB_URL`` set must exit NON-ZERO *before any DB write* instead of
silently writing the dev scratch DB. The explicit opt-ins (a real
``WORKBENCH_DB_URL`` or ``WORKBENCH_ALLOW_DEV_DB=1``) keep dev / CI / tests
working.
"""

from __future__ import annotations

import pytest

from workbench_api.backtests import canonical as canonical_mod
from workbench_api.backtests import worker as worker_mod
from workbench_api.db.require_production_db import (
    ALLOW_DEV_DB_ENV,
    ScratchDatabaseError,
    require_production_db,
)
from workbench_api.settings import DEFAULT_DEV_DB_URL


def _force_scratch_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make settings resolve to the DEFAULT_DEV_DB_URL scratch fallback (i.e.
    WORKBENCH_DB_URL effectively unset) with no dev opt-in."""

    monkeypatch.delenv("WORKBENCH_DB_URL", raising=False)
    monkeypatch.delenv(ALLOW_DEV_DB_ENV, raising=False)


# --- the guard function ---------------------------------------------------


def test_guard_raises_on_scratch_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_scratch_env(monkeypatch)
    with pytest.raises(ScratchDatabaseError) as excinfo:
        require_production_db(entrypoint="canonical")
    msg = str(excinfo.value)
    assert "::error::" in msg
    assert "WORKBENCH_DB_URL is unset" in msg
    assert DEFAULT_DEV_DB_URL in msg


def test_guard_allows_explicit_production_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DB_URL", "sqlite:////var/lib/workbench/db/workbench.db")
    monkeypatch.delenv(ALLOW_DEV_DB_ENV, raising=False)
    url = require_production_db(entrypoint="worker")
    assert url == "sqlite:////var/lib/workbench/db/workbench.db"


def test_guard_allows_dev_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_scratch_env(monkeypatch)
    monkeypatch.setenv(ALLOW_DEV_DB_ENV, "1")
    # Opt-in deliberately permits the scratch DB; no raise.
    assert require_production_db(entrypoint="canonical") == DEFAULT_DEV_DB_URL


@pytest.mark.parametrize("flag", ["true", "YES", "On", "1"])
def test_guard_opt_in_is_case_insensitive(
    monkeypatch: pytest.MonkeyPatch, flag: str
) -> None:
    _force_scratch_env(monkeypatch)
    monkeypatch.setenv(ALLOW_DEV_DB_ENV, flag)
    assert require_production_db(entrypoint="worker") == DEFAULT_DEV_DB_URL


def test_guard_opt_in_ignores_falsey_values(monkeypatch: pytest.MonkeyPatch) -> None:
    _force_scratch_env(monkeypatch)
    monkeypatch.setenv(ALLOW_DEV_DB_ENV, "0")
    with pytest.raises(ScratchDatabaseError):
        require_production_db(entrypoint="canonical")


# --- the CLI entrypoints exit non-zero WITHOUT touching the DB ------------


def test_canonical_main_exits_nonzero_and_never_opens_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_scratch_env(monkeypatch)

    def _boom() -> object:  # pragma: no cover - must never run
        raise AssertionError("get_engine() called — guard did not fire first")

    monkeypatch.setattr(canonical_mod, "get_engine", _boom)
    assert canonical_mod.main([]) == 1


def test_worker_main_exits_nonzero_and_never_opens_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_scratch_env(monkeypatch)

    def _boom() -> object:  # pragma: no cover - must never run
        raise AssertionError("get_engine() called — guard did not fire first")

    monkeypatch.setattr(worker_mod, "get_engine", _boom)
    assert worker_mod.main(poll_seconds=0.0, max_iterations=1) == 1
