"""Workbench settings loader with explicit env-var allowlist (B020).

B020 deliberately reads no environment variables. The empty allowlist below is
the enforcement surface: any future env var must be added here AND consumed via
the typed Settings model. The safety test
``tests/safety/test_settings_env_allowlist.py`` asserts the allowlist contents.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_ENV_VARS: frozenset[str] = frozenset()
"""Names of environment variables the workbench backend is permitted to read.

B020 holds this empty by design. Subsequent batches add entries here and the
matching typed field on ``Settings``.
"""


class Settings(BaseSettings):
    """Typed runtime configuration for the workbench backend.

    Fields are intentionally absent in B020. The allowlist mechanism (and the
    associated safety test) keep this surface honest as features land.
    """

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        extra="forbid",
    )


def get_settings() -> Settings:
    """Return a fresh Settings instance. Cheap; not memoized in B020."""

    return Settings()
