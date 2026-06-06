"""B044 F001 — trade/ package install wiring (deploy artifact + CI).

The recommendations precompute timer (B044 F002) imports
``trade.backtest.master_portfolio`` for real scoring, so the repo-root
``trade/`` package must reach the production VM venv. This batch's decision
(2026-06-06): install ``trade`` into ``/opt/workbench/.venv`` alongside
``workbench_api`` (evaluator position A). The request path must NEVER import
trade — that boundary moves from "physically absent" to an AST guard (F003)
now that trade ships to the venv.

These guards pin the install chain so it can't silently regress:

1. The root ``pyproject.toml`` packages ``trade`` and declares its direct
   third-party imports (pandas / numpy) as explicit deps (v0.9.29 §12.8).
2. The deploy workflow builds the trade wheel and ships it into the release.
3. ``deploy.sh`` installs the trade wheel into the venv (best-effort).
4. The backend CI installs the trade package so precompute tests resolve.

We grep the artifacts (they build/run in CI / on the VM, not here).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
ROOT_PYPROJECT = REPO_ROOT / "pyproject.toml"
DEPLOY_SH = REPO_ROOT / "workbench" / "deploy" / "scripts" / "deploy.sh"
DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "workbench-deploy.yml"
BACKEND_CI = REPO_ROOT / ".github" / "workflows" / "workbench-backend.yml"


def test_root_pyproject_packages_trade_with_explicit_deps() -> None:
    data = tomllib.loads(ROOT_PYPROJECT.read_text(encoding="utf-8"))
    assert data["project"]["name"] == "trade"
    packages = data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"]
    assert "trade" in packages, "root pyproject must package the trade/ dir"
    # trade imports pandas + numpy directly → explicit runtime deps (§12.8).
    dep_names = {
        dep.split(">")[0].split("=")[0].split("[")[0].strip()
        for dep in data["project"]["dependencies"]
    }
    assert "pandas" in dep_names
    assert "numpy" in dep_names, "trade imports numpy directly — declare it explicitly"


def test_deploy_workflow_builds_and_ships_trade_wheel() -> None:
    text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    # Build step (repo-root wheel) + stage/ship into the release tree.
    assert "Build trade package (wheel)" in text
    assert "python -m build --wheel" in text
    assert "rsync -a dist/trade-*.whl" in text


def test_deploy_sh_installs_trade_wheel_into_venv() -> None:
    text = DEPLOY_SH.read_text(encoding="utf-8")
    # The wheel is resolved from the release trade-dist/ dir and pip-installed
    # into the shared venv via ${VENV_PIP}.
    assert "trade-dist/trade-*.whl" in text
    assert "install trade package into /opt/workbench/.venv" in text
    # Best-effort: skips (does not hard-fail) when the wheel is absent.
    assert "skipping (B044 F001" in text


def test_backend_ci_installs_trade_package() -> None:
    text = BACKEND_CI.read_text(encoding="utf-8")
    # CI installs the repo-root trade package (working-directory is
    # workbench/backend → `../..` is the repo root) so precompute tests resolve.
    assert "pip install ../.." in text
