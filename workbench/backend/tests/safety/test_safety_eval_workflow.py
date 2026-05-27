"""B032 F002 — AI Safety Eval workflow + deploy-gate wiring guard.

Pin the two-file invariant so the safety eval CI gate cannot silently
detach from the deploy chain:

1. ``.github/workflows/ai-safety-eval.yml`` is well-formed YAML, scopes
   its ``paths`` trigger to the LLM module + the red-team dataset,
   wires ``AIGC_GATEWAY_API_KEY`` from secrets, and actually runs the
   red-team pytest file.
2. ``.github/workflows/workbench-deploy.yml`` lists ``AI Safety Eval``
   among the upstream workflows that arm a deploy (permanent boundary
   **(n)** — a red safety eval must block production).

A regression on either side either (a) lets a malformed safety eval
sample skip the CI run because the path is wrong, or (b) lets a red
safety eval still arm a production deploy. Both are silent failures of
the gate — hence loud pytest assertions here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]

REPO_ROOT = Path(__file__).resolve().parents[4]
SAFETY_EVAL_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ai-safety-eval.yml"
WORKBENCH_DEPLOY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "workbench-deploy.yml"


def _read(path: Path) -> str:
    if not path.is_file():
        pytest.fail(
            f"Expected workflow file at {path.relative_to(REPO_ROOT)} but "
            "none was found. B032 F002 wiring drift: check whether the "
            "workflow moved."
        )
    return path.read_text(encoding="utf-8")


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse a workflow file as YAML — surfaces a syntax error before any
    individual assertion does."""

    text = _read(path)
    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        pytest.fail(
            f"{path.relative_to(REPO_ROOT)} is not valid YAML: {exc}"
        )
    assert isinstance(loaded, dict), (
        f"{path.relative_to(REPO_ROOT)} parsed to {type(loaded).__name__}, "
        "expected a top-level mapping"
    )
    return loaded


# ---------------------------------------------------------------------------
# ai-safety-eval.yml shape
# ---------------------------------------------------------------------------


def test_safety_eval_workflow_yaml_parses() -> None:
    """A typo in the workflow file would either fail at runtime
    (silently disabling the gate) or at every CI run. Catch it here."""

    workflow = _load_yaml(SAFETY_EVAL_WORKFLOW)
    assert workflow.get("name") == "AI Safety Eval"


def test_safety_eval_workflow_paths_include_llm_and_dataset() -> None:
    """The paths trigger must cover every directory whose change could
    invalidate the safety eval result."""

    text = _read(SAFETY_EVAL_WORKFLOW)
    for required_path in (
        "workbench/backend/workbench_api/llm/**",
        "workbench/backend/tests/safety/test_ai_advisor_red_team.py",
        "data/safety-evals/**",
        ".github/workflows/ai-safety-eval.yml",
    ):
        assert required_path in text, (
            f"ai-safety-eval.yml paths trigger missing {required_path!r}; "
            "any change to that location must re-run the safety eval CI"
        )


def test_safety_eval_workflow_injects_aigc_gateway_api_key() -> None:
    """The Sonnet judge call needs the gateway key once B036 lands; the
    workflow must already source it from secrets so a red CI on the
    advisor MVP day is not a missing-env regression."""

    text = _read(SAFETY_EVAL_WORKFLOW)
    needle = "AIGC_GATEWAY_API_KEY: ${{ secrets.AIGC_GATEWAY_API_KEY }}"
    assert needle in text, (
        "ai-safety-eval.yml must inject AIGC_GATEWAY_API_KEY from repo "
        "secrets at the job env level so the test can call the LLM gateway "
        "once B036 wires a real advisor."
    )


def test_safety_eval_workflow_runs_red_team_pytest() -> None:
    """The workflow must actually invoke the parametrized red-team
    pytest file (otherwise the gate is cosmetic)."""

    text = _read(SAFETY_EVAL_WORKFLOW)
    assert "tests/safety/test_ai_advisor_red_team.py" in text


def test_safety_eval_workflow_force_node24_flag_set() -> None:
    """Inherit the framework-wide forward-compat flag so JS-based
    actions run on Node 24 ahead of the 2026-09 Node 20 deprecation."""

    text = _read(SAFETY_EVAL_WORKFLOW)
    assert 'FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"' in text


# ---------------------------------------------------------------------------
# workbench-deploy.yml — gate inclusion
# ---------------------------------------------------------------------------


def test_workbench_deploy_includes_ai_safety_eval_workflow() -> None:
    """Permanent boundary (n): a red safety eval must block deploy. The
    workflow_run trigger lists every upstream workflow whose green main
    run can arm a deploy; the conditional re-checks
    ``conclusion == 'success'``. Adding ``AI Safety Eval`` to that list
    extends the gate to the safety eval result."""

    workflows = _deploy_trigger_workflows()
    assert "AI Safety Eval" in workflows, (
        "workbench-deploy.yml workflow_run.workflows must include "
        f"'AI Safety Eval' so a red safety eval blocks deploy; got "
        f"{workflows!r}"
    )


def test_workbench_deploy_still_gates_backend_and_frontend() -> None:
    """Adding AI Safety Eval must not displace the pre-existing
    Backend/Frontend CI gates; the deploy is the conjunction of all
    three (any one red can keep production safe)."""

    workflows = _deploy_trigger_workflows()
    for name in ("Workbench Backend CI", "Workbench Frontend CI", "AI Safety Eval"):
        assert name in workflows, (
            f"workbench-deploy.yml workflow_run.workflows must keep {name!r}; "
            f"current list: {workflows!r}"
        )


def _deploy_trigger_workflows() -> list[Any]:
    """Extract the deploy workflow's ``workflow_run.workflows`` list.

    YAML 1.1 parses the bare key ``on:`` as the Python boolean ``True``,
    so the top-level dict key is not the string ``"on"``. We pull the
    triggers via the raw mapping API to tolerate both spellings; this
    keeps the test resilient to a future YAML 1.2 / quoting fix.
    """

    workflow: Any = _load_yaml(WORKBENCH_DEPLOY_WORKFLOW)
    triggers: Any = workflow.get("on") or workflow.get(True) or {}
    workflow_run: Any = triggers.get("workflow_run") if isinstance(triggers, dict) else None
    if not isinstance(workflow_run, dict):
        pytest.fail(
            "workbench-deploy.yml is missing the workflow_run trigger; safety "
            "eval cannot arm a deploy without it"
        )
    workflows = workflow_run.get("workflows", [])
    assert isinstance(workflows, list), (
        "workbench-deploy.yml workflow_run.workflows must be a list; "
        f"got {type(workflows).__name__}"
    )
    return workflows
