"""Alembic env for the workbench backend.

Pulls ``WORKBENCH_DB_URL`` from the same Settings model the FastAPI app
uses, so the prod systemd unit and the local dev override go through one
allowlisted gate. ``target_metadata`` is wired to the project's declarative
Base so ``alembic revision --autogenerate`` will see future schema diffs
the moment a new model lands in ``workbench_api.db.models``.
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from workbench_api.db.models import Base  # noqa: F401  (imports register the ORM models)
from workbench_api.settings import get_settings

config = context.config

if config.config_file_name is not None:
    # ``disable_existing_loggers=False`` keeps test-suite-wide caplog /
    # service loggers intact. The default ``True`` value silently
    # disables every logger created before this fileConfig call, which
    # turns into spooky-action-at-a-distance: any test (B027 F002
    # test_budget_log_repo.test_alembic_upgrade_creates_tiingo_budget_log_table
    # was the first repro) that drives alembic upgrade in-process would
    # kill the cost_guard / dashboard / etc. loggers that downstream
    # tests rely on for caplog assertions.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

# Override the placeholder URL in alembic.ini with the allowlisted env var.
config.set_main_option("sqlalchemy.url", get_settings().WORKBENCH_DB_URL)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
