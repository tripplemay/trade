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
    The post-alembic schema check must reference every workbench table
    that production code depends on. B023 F001 (v0.9.25 #1b) extended
    the asserted set from the original 3 B021/B022 tables to the full
    6 — the new B023 execution-workflow tables (order_ticket,
    fill_journal_entry, account_snapshot) must also be present."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    required = (
        "account",
        "backlog_entry",
        "snapshot_meta",
        "order_ticket",
        "fill_journal_entry",
        "account_snapshot",
        # B048-OPS1 F001 — the 0007-0011 era tables prod was missing in
        # Finding #1 (alembic stalled at 0006). price_history (0011) is the
        # concrete Finding #1 table; the rest round out the gap.
        "market_context_observation",
        "advisor_recommendation",
        "price_snapshot",
        "recommendation_snapshot",
        "price_history",
    )
    for table in required:
        assert table in text, (
            f"deploy.sh post-alembic check must verify presence of '{table}' "
            f"table — missing reference"
        )


def test_deploy_script_asserts_alembic_at_head_after_upgrade() -> None:
    """B048-OPS1 F001 (core durable defense) — deploy.sh must assert
    ``alembic current == heads`` after the upgrade and fail LOUDLY
    (``::error::`` + non-zero exit) on a mismatch. This turns the Finding #1
    silent stall (prod stuck at 0006) into a visible deploy failure."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "get_current_heads" in text, (
        "deploy.sh must compare the DB's current revision to the migration "
        "tree head after `alembic upgrade head`"
    )
    assert "ScriptDirectory" in text, (
        "deploy.sh must resolve the migration tree head via alembic's "
        "ScriptDirectory to compare against the DB"
    )
    # The assert must fail loudly — GitHub Actions error annotation + exit.
    assert "::error::alembic NOT at head" in text, (
        "the alembic==head assertion must emit a `::error::` annotation so a "
        "silent stall becomes a visible failure"
    )


def test_deploy_script_fails_when_db_url_missing_from_readable_env() -> None:
    """B048-OPS1 F001 — a readable env file (the prod path) with no
    WORKBENCH_DB_URL must fail the deploy, not silently migrate the
    DEFAULT_DEV_DB_URL scratch DB (the B022 F014 / Finding #1 vector)."""

    text = DEPLOY_SH.read_text(encoding="utf-8")
    assert "::error::${ENV_FILE} is readable but WORKBENCH_DB_URL is unset" in text, (
        "deploy.sh must hard-fail when the env file is readable but does not "
        "export WORKBENCH_DB_URL"
    )
