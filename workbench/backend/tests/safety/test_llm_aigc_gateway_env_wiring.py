"""B031 F001 — AIGC_GATEWAY_API_KEY four-place wiring guard.

Per the framework v0.9.30 §12.9 production-secret rule (originally
"three-place" — extended to four for B027/B029/B030/B031), every
backend-only secret must surface in four coordinated places so a
restart on the production VM cannot leave the workbench wedged on a
missing key:

1. ``workbench/backend/.env.example`` — local dev template.
2. ``workbench/backend/workbench_api/settings.py`` — typed field on
   the ``Settings`` model + allowlist entry.
3. ``workbench/deploy/scripts/deploy.sh`` — pre-flight check that
   fails the deploy when ``/etc/workbench/workbench.env`` does not
   carry the secret (avoids the "deploy succeeds, first request
   crashes" failure mode).
4. ``.github/workflows/bootstrap-env.yml`` — heredoc body that
   writes ``AIGC_GATEWAY_API_KEY=$AIGC_GATEWAY_API_KEY`` into the
   VM's env file (sourced from the GitHub repo secret).

A regression on any of those four places either degrades the LLM
gateway to dev-only at runtime or hides the misconfiguration until
the first advisor request — both unacceptable. The tests below
fail loudly on any drift.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
ENV_EXAMPLE_PATH = REPO_ROOT / "workbench" / "backend" / ".env.example"
SETTINGS_PATH = (
    REPO_ROOT / "workbench" / "backend" / "workbench_api" / "settings.py"
)
DEPLOY_SH_PATH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"
BOOTSTRAP_WORKFLOW_PATH = (
    REPO_ROOT / ".github" / "workflows" / "bootstrap-env.yml"
)


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.fail(
            f"Expected file at {path.relative_to(REPO_ROOT)} but none was found. "
            "B031 F001 wiring drift: check whether the path moved."
        )
    return path.read_text(encoding="utf-8")


# Place 1 — .env.example -------------------------------------------------


def test_env_example_declares_aigc_gateway_api_key() -> None:
    """The dev template must declare an empty ``AIGC_GATEWAY_API_KEY=``
    line so a fresh clone surfaces the missing key at first run."""

    content = _read(ENV_EXAMPLE_PATH)
    assert "AIGC_GATEWAY_API_KEY=" in content


def test_env_example_documents_b031_and_creator_helper() -> None:
    """The dev comment must mention B031 + ``mcp__aigc-gateway__create_api_key``
    so a maintainer reading the file knows where the key comes from."""

    content = _read(ENV_EXAMPLE_PATH)
    assert "B031" in content
    assert "mcp__aigc-gateway__create_api_key" in content


# Place 2 — settings.py --------------------------------------------------


def test_settings_declares_aigc_gateway_api_key_field() -> None:
    """The pydantic ``Settings`` model must expose a typed field so the
    allowlist + boundary assertions in ``test_settings_env_allowlist``
    stay green."""

    content = _read(SETTINGS_PATH)
    assert "AIGC_GATEWAY_API_KEY" in content
    # Both the allowlist set entry AND the typed field must be present.
    assert '"AIGC_GATEWAY_API_KEY"' in content
    assert "AIGC_GATEWAY_API_KEY: str | None = None" in content


# Place 3 — deploy.sh pre-flight -----------------------------------------


def test_deploy_sh_has_aigc_gateway_preflight_check() -> None:
    """``deploy.sh`` must abort the deploy when the production env file
    lacks the gateway API key — same shape as the TIINGO_API_KEY (exit
    66) and SEC_EDGAR_CONTACT_EMAIL (exit 67) checks. Exit code 68 is
    the B031 slot."""

    content = _read(DEPLOY_SH_PATH)
    assert "AIGC_GATEWAY_API_KEY" in content
    assert "exit 68" in content
    # Pre-flight must run BEFORE the actual alembic invocation so a
    # missing key surfaces immediately. Match the invocation line
    # (`-m alembic upgrade head`) rather than the prose comment block
    # earlier in the file (the same pattern test_deploy_alembic_env_load
    # uses for the alembic guard).
    aigc_idx = content.find("AIGC_GATEWAY_API_KEY")
    alembic_idx = content.find("-m alembic upgrade head")
    assert aigc_idx != -1 and alembic_idx != -1
    assert aigc_idx < alembic_idx, (
        "AIGC_GATEWAY_API_KEY pre-flight must run before `alembic "
        "upgrade head` so the deploy aborts immediately when the key "
        "is missing — otherwise the migration runs but the first LLM "
        "call still fails."
    )


# Place 4 — bootstrap-env.yml -------------------------------------------


def test_bootstrap_workflow_inlines_aigc_gateway_secret() -> None:
    """The bootstrap workflow must wire the GitHub repo secret into
    the env-file heredoc, AND the required-keys validation loop must
    include ``AIGC_GATEWAY_API_KEY`` so a missing repo secret fails
    the bootstrap run loudly."""

    content = _read(BOOTSTRAP_WORKFLOW_PATH)
    # Step env block reads the repo secret.
    assert (
        "AIGC_GATEWAY_API_KEY: ${{ secrets.AIGC_GATEWAY_API_KEY }}" in content
    ), "bootstrap-env.yml step env block must read AIGC_GATEWAY_API_KEY from secrets"
    # Heredoc body writes the env-file line.
    assert "AIGC_GATEWAY_API_KEY=$AIGC_GATEWAY_API_KEY" in content, (
        "bootstrap-env.yml heredoc must write the AIGC_GATEWAY_API_KEY "
        "line into /etc/workbench/workbench.env"
    )
    # Required-key validation loop covers the new key.
    assert "AIGC_GATEWAY_API_KEY;" in content or "AIGC_GATEWAY_API_KEY " in content, (
        "bootstrap-env.yml required-keys for-loop must include "
        "AIGC_GATEWAY_API_KEY (catches the failure mode where the "
        "repo secret is empty)"
    )
