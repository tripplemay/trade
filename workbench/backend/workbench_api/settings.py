"""Workbench backend settings with explicit env-var allowlist.

The allowlist is the enforcement surface: any env var consumed by the backend
must appear in ``ALLOWED_ENV_VARS`` *and* be declared as a typed field on
``Settings``. ``tests/safety/test_settings_env_allowlist.py`` keeps the two
ends in sync.

B021 F001 introduces the first real entries: NextAuth's JWT signing secret
(shared with the frontend so the backend can verify session cookies) and the
single-user allowlist email.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_ENV_VARS: frozenset[str] = frozenset(
    {
        "NEXTAUTH_SECRET",
        "ALLOWED_USER_EMAIL",
        "WORKBENCH_DB_URL",
        "SENTRY_DSN",
        "WORKBENCH_BACKUP_LOG",
        "WORKBENCH_LOG_DIR",
        "WORKBENCH_REPORTS_DIR",
    }
)
"""Environment variables the workbench backend is permitted to read.

Each entry has a matching typed field on ``Settings`` below. Adding a new
variable requires a deliberate review of the safety boundary it widens.
"""

DEFAULT_DEV_DB_URL: str = "sqlite:///./workbench-dev.db"
"""Local dev fallback so a fresh clone runs without ``/var/lib/workbench/``.

Production sets ``WORKBENCH_DB_URL=sqlite:////var/lib/workbench/db/workbench.db``
via the systemd EnvironmentFile (B021 F003).
"""

DEFAULT_BACKUP_LOG_PATH: str = "/var/log/workbench/backup.log"
DEFAULT_LOG_DIR: str = "/var/log/workbench"
DEFAULT_REPORTS_DIR: str = "docs/test-reports"
"""B022 F006 — Dashboard's recent-reports scanner roots here.

Resolved relative to the backend's CWD on the VM; production deploy can
override via systemd EnvironmentFile when reports are staged elsewhere.
A missing or empty directory degrades to an empty list (the handler
treats "no reports surfaced" as a valid empty state, not an error).
"""


class Settings(BaseSettings):
    """Typed runtime configuration for the workbench backend.

    Fields are all optional so the FastAPI app boots in dev even when the
    OAuth + allowlist plumbing is not yet configured. Routes that require
    authentication enforce non-emptiness at request time (see
    ``workbench_api.auth.jwt_validator``).
    """

    NEXTAUTH_SECRET: str | None = None
    ALLOWED_USER_EMAIL: str | None = None
    WORKBENCH_DB_URL: str = DEFAULT_DEV_DB_URL
    # Observability (B021 F006). Sentry DSN is opt-in — unset is no-op so
    # the dev path stays vendor-free. The backup log path is parsed by
    # `observability.backup_status` to surface `last_backup_*` on /api/health.
    SENTRY_DSN: str | None = None
    WORKBENCH_BACKUP_LOG: str = DEFAULT_BACKUP_LOG_PATH
    WORKBENCH_LOG_DIR: str = DEFAULT_LOG_DIR
    # B022 F006 — directory the Dashboard scans for `recent_reports`.
    WORKBENCH_REPORTS_DIR: str = DEFAULT_REPORTS_DIR

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        extra="forbid",
    )


def get_settings() -> Settings:
    """Return a fresh Settings instance. Cheap; not memoized."""

    return Settings()
