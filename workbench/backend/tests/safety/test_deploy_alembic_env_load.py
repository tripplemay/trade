"""Safety regression — deploy.sh must source the workbench env file
before running alembic.

B022 F014 fixing-round 4 root cause: the SSH session that runs
``deploy.sh`` does not load ``/etc/workbench/workbench.env`` (only the
systemd unit does, via ``EnvironmentFile=``). When alembic ran without
``WORKBENCH_DB_URL`` set, ``Settings()`` fell back to
``DEFAULT_DEV_DB_URL = "sqlite:///./workbench-dev.db"``, so the
migration created tables in a per-release scratch file that the live
systemd backend never opened. The production DB at
``/var/lib/workbench/db/workbench.db`` stayed empty and B022 routes
hit ``OperationalError: no such table: snapshot_meta / backlog_entry``
at request time (visible via /api/debug/recent-errors round-3).

This test pins the deploy.sh fix so the env-source step + the
post-alembic schema verifier can never silently regress. We grep the
literal commands instead of executing the script because the script
expects a release dir argument and runs on the production VM.
"""

from __future__ import annotations

from pathlib import Path

DEPLOY_SH = (
    Path(__file__).resolve().parents[4]
    / "workbench"
    / "deploy"
    / "scripts"
    / "deploy.sh"
)


def test_deploy_script_exists() -> None:
    assert DEPLOY_SH.exists(), f"missing deploy script: {DEPLOY_SH}"


def test_deploy_script_sources_env_before_alembic() -> None:
    """deploy.sh must export the env-file's variables into the alembic
    subprocess. We accept either the explicit ``set -a; . file; set +a``
    pattern or an equivalent ``export $(grep -v ^# file | xargs)`` if
    someone refactors later — both populate the environment alembic
    inherits."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    sources_env = (
        ". \"${ENV_FILE}\"" in text
        or ". \"$ENV_FILE\"" in text
        or "source \"${ENV_FILE}\"" in text
        or "source \"$ENV_FILE\"" in text
    )
    assert sources_env, "deploy.sh must source the env file before alembic"

    set_a = "set -a" in text
    set_plus_a = "set +a" in text
    assert set_a and set_plus_a, (
        "deploy.sh must wrap the env source with `set -a` / `set +a` so the "
        "variables get exported into the alembic subprocess"
    )


def test_deploy_script_references_alembic_after_env_load() -> None:
    """The env load must come *before* the alembic invocation; otherwise
    alembic still sees an unset WORKBENCH_DB_URL."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    env_idx = text.find(". \"${ENV_FILE}\"")
    # Match the actual invocation, not the prose comment block above it.
    alembic_idx = text.find("-m alembic upgrade head")
    assert env_idx != -1, "missing `. \"${ENV_FILE}\"` source line"
    assert alembic_idx != -1, "missing `-m alembic upgrade head` invocation"
    assert env_idx < alembic_idx, (
        "env file must be sourced before `-m alembic upgrade head`"
    )


def test_deploy_script_verifies_required_tables_post_alembic() -> None:
    """Catches the future regression where the env path drifts again.
    The post-alembic schema check must reference all three tables that
    B021+B022 depend on."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    for table in ("account", "backlog_entry", "snapshot_meta"):
        assert table in text, (
            f"deploy.sh post-alembic check must verify presence of '{table}' "
            f"table — missing reference"
        )
