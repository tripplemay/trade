"""B035 F001 — FRED_API_KEY + ALPHAVANTAGE_API_KEY four-place wiring guard.

Per framework v0.9.30 §12.9, every backend-only secret must surface in
four coordinated places so a production VM restart can't wedge on a
missing key:

1. ``workbench/backend/.env.example`` — local dev template.
2. ``workbench/backend/workbench_api/settings.py`` — typed field +
   allowlist entry.
3. ``workbench/deploy/scripts/deploy.sh`` — pre-flight check that aborts
   the deploy when the env file lacks the secret (FRED → exit 69,
   Alpha Vantage → exit 70).
4. ``.github/workflows/bootstrap-env.yml`` — env-block read + heredoc
   line + required-keys validation loop.

Mirrors ``test_llm_aigc_gateway_env_wiring`` (B031) for the two B035
market-context secrets.
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
BOOTSTRAP_WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "bootstrap-env.yml"

# secret name → deploy.sh pre-flight exit code slot.
SECRETS = {"FRED_API_KEY": "exit 69", "ALPHAVANTAGE_API_KEY": "exit 70"}


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.fail(f"Expected file at {path.relative_to(REPO_ROOT)} but none found.")
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("secret", sorted(SECRETS))
def test_env_example_declares_secret(secret: str) -> None:
    assert f"{secret}=" in _read(ENV_EXAMPLE_PATH)


@pytest.mark.parametrize("secret", sorted(SECRETS))
def test_settings_declares_typed_field_and_allowlist(secret: str) -> None:
    content = _read(SETTINGS_PATH)
    assert f'"{secret}"' in content  # allowlist set entry
    assert f"{secret}: str | None = None" in content  # typed field


@pytest.mark.parametrize("secret", sorted(SECRETS))
def test_deploy_preflight_before_alembic(secret: str) -> None:
    content = _read(DEPLOY_SH_PATH)
    assert SECRETS[secret] in content
    secret_idx = content.find(secret)
    alembic_idx = content.find("-m alembic upgrade head")
    assert secret_idx != -1 and alembic_idx != -1
    assert secret_idx < alembic_idx, (
        f"{secret} pre-flight must run before `alembic upgrade head`."
    )


@pytest.mark.parametrize("secret", sorted(SECRETS))
def test_bootstrap_workflow_wires_secret(secret: str) -> None:
    content = _read(BOOTSTRAP_WORKFLOW_PATH)
    assert f"{secret}: ${{{{ secrets.{secret} }}}}" in content
    assert f"{secret}=${secret}" in content
    assert f"{secret};" in content or f"{secret} " in content  # required-keys loop


def test_env_example_documents_b035() -> None:
    content = _read(ENV_EXAMPLE_PATH)
    assert "B035" in content
    assert "alphavantage" in content.lower()
    assert "fred" in content.lower()
