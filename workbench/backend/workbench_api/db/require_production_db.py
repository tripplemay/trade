"""B047-OPS1 F001 — env hard-fail guard for the write-CLI entrypoints.

The backtest worker daemon (``backtests.worker``) and the canonical report
generator (``backtests.canonical``) are import-``trade`` CLIs that **write** to
the workbench DB. Unlike the FastAPI app (always run under systemd with
``EnvironmentFile=``) and ``alembic upgrade head`` in ``deploy.sh`` (which sources
the env file + hard-fails when ``WORKBENCH_DB_URL`` is unset — B048-OPS1 / B022
F014), these CLIs can be run by hand.

When run without the env, ``settings.WORKBENCH_DB_URL`` silently falls back to
``DEFAULT_DEV_DB_URL`` — a dev *scratch* SQLite file — so the job writes its
reports to the wrong DB while the API reads prod. That is exactly the B047
re-verify mis-diagnosis: a bare ``python -m workbench_api.backtests.canonical``
wrote scratch, ``/api/reports`` read prod → 0 items (wrongly blamed on the read
path; the real cause was the env writing the wrong DB).

This guard makes that failure **loud** instead of silent: when the resolved DB
URL is the ``DEFAULT_DEV_DB_URL`` scratch fallback and the caller has not
explicitly opted into the dev DB, it raises so the CLI exits non-zero
(``::error::``) **before any DB write**.

Explicit opt-in (so dev / CI / tests are never broken):
- set ``WORKBENCH_DB_URL`` to any non-default value (tests point it at a
  temp / in-memory sqlite), or
- set ``WORKBENCH_ALLOW_DEV_DB=1`` to deliberately run against the scratch DB.

Boundary: the guard only *inspects* the resolved URL — it never opens a
connection or writes. (B048-OPS1 env-url hard-fail family / v0.9.21 诚实失败.)
"""

from __future__ import annotations

import os

from workbench_api.settings import DEFAULT_DEV_DB_URL, get_settings

ALLOW_DEV_DB_ENV = "WORKBENCH_ALLOW_DEV_DB"
_TRUTHY = frozenset({"1", "true", "yes", "on"})


class ScratchDatabaseError(RuntimeError):
    """Raised when a write CLI would silently target the dev scratch DB."""


def _dev_opt_in() -> bool:
    """Read the opt-in flag directly from the environment (not a Settings
    field — it gates a CLI, not backend config, so it stays out of the
    ALLOWED_ENV_VARS surface, mirroring ``WORKBENCH_BACKTEST_POLL_SECONDS``)."""

    return os.environ.get(ALLOW_DEV_DB_ENV, "").strip().lower() in _TRUTHY


def require_production_db(*, entrypoint: str) -> str:
    """Assert the resolved ``WORKBENCH_DB_URL`` is not the silent dev-scratch
    fallback. Return the URL on success; raise :class:`ScratchDatabaseError`
    otherwise.

    Call at the top of a write-CLI's ``main()`` — before opening any session —
    so the process exits non-zero rather than writing to ``./workbench-dev.db``
    while the live API reads prod.
    """

    url = get_settings().WORKBENCH_DB_URL
    if url == DEFAULT_DEV_DB_URL and not _dev_opt_in():
        raise ScratchDatabaseError(
            f"::error::{entrypoint}: WORKBENCH_DB_URL is unset — this would write "
            f"the DEFAULT_DEV_DB_URL scratch DB ({url}), not prod. The report "
            "would land in the wrong DB while the API reads prod (B047 re-verify "
            "root cause). Run this via systemd "
            "(EnvironmentFile=/etc/workbench/workbench.env) or `source` that env "
            "file so WORKBENCH_DB_URL points at prod. For local dev / CI, set "
            f"{ALLOW_DEV_DB_ENV}=1 to deliberately opt into the scratch DB."
        )
    return url
