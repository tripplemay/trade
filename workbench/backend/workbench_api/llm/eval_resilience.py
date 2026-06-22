"""B073 F002 — AI Safety Eval gateway resilience (infra-unreachable vs unsafe).

Motivation: a single external LLM-gateway outage (2026-06-21 ``aigc.guangai.ai``
503/429) reddened the AI Safety Eval CI and blocked the deploy of unrelated code
(a clock change that never touches the advisor). This module separates two
fundamentally different outcomes so the gate stays honest **without weakening the
safety boundary** (B073 §0 — welded):

* **advisor unsafe** (the Sonnet judge sets ``fail_triggered``) → always a hard
  failure. Never relaxed.
* **gateway unreachable** (503 / 429 / timeout / connection error, after the
  gateway's own bounded retries) → *infrastructure*, not a safety conclusion.
  The eval reports ``infra-unavailable, safety UNVERIFIED`` and lets the test
  skip (CI green) so an outage does not hard-block an unrelated deploy —
  **except** when this change touches AI-advisor logic (``llm/`` / ``advisor/``
  paths): an unverified advisor change while the gateway is down still **blocks**
  (``unreachable != safe pass``).

The classification + per-sample evaluation live here as pure, unit-testable
functions (rather than inline in the pytest module) so Codex F003 can mutate them
and prove the safety teeth: a 503 must skip, an unsafe advisor must hard-fail, an
advisor-path change + unreachable must block, and a non-infra error (4xx / auth)
must still surface.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from workbench_api.advisor.grounding import grounding_from_synthetic
from workbench_api.advisor.service import AdvisorService
from workbench_api.llm.gateway import LLMGateway
from workbench_api.llm.judge import judge_output

# Status codes that mean "the gateway won't / can't give us a usable verdict for
# an operational reason", i.e. infrastructure — NOT a verdict about advisor
# content and NOT a malformed-request bug on our side:
#   * 429 — rate limited (the 2026-06-21 incident also threw these on retry)
#   * 5xx — gateway / upstream server error
#   * 402 — Payment Required: the gateway account is out of credit, so it
#           refuses to serve us. Observed 2026-06-22 in the AI Safety Eval. This
#           is operational (top up credit), not a safety result — there is no
#           advisor output at all, so it can never mask an unsafe verdict.
#   * 408 — server-side request timeout, the peer counterpart of the client
#           ``httpx.TimeoutException`` already covered by TransportError below.
# Any OTHER 4xx (400/404/422/...) is a *caller* bug (malformed request) and MUST
# surface as a red failure, never be mistaken for an outage. 401/403 surface
# from the gateway as ``_AuthFailure`` (a RuntimeError), also NOT infra — a bad
# key is our config to fix, not a transient outage.
_INFRA_STATUS_CODES: frozenset[int] = frozenset({402, 408, 429, *range(500, 600)})

# Code paths whose change requires re-verifying advisor safety. Matched as a
# substring so the check is agnostic to whether the diff is reported repo-root-
# relative (``workbench/backend/workbench_api/llm/...``) or package-relative.
# The red-team test file, the dataset, and the workflow YAML are deliberately
# NOT here — editing them does not change advisor behaviour.
ADVISOR_CODE_SUBPATHS: tuple[str, ...] = (
    "workbench_api/llm/",
    "workbench_api/advisor/",
)

# Modules that live under ``llm/`` but are the eval HARNESS, not advisor
# request/validation logic: they are imported ONLY by the safety test suite,
# never by the production advisor path, so changing them cannot change advisor
# output. Excluded so a change to the resilience policy itself does not
# over-block on an outage. This stays fail-safe: any OTHER ``llm/`` or
# ``advisor/`` change still flags (an unknown new file defaults to flagged).
ADVISOR_PATH_EXCLUSIONS: tuple[str, ...] = (
    "workbench_api/llm/eval_resilience.py",
)

# Env var the AI Safety Eval workflow sets (computed from the commit diff) so the
# live test knows whether THIS change touched advisor logic. Unset → treated as
# "not changed" for local dev runs; CI sets it explicitly every run.
ADVISOR_CHANGED_ENV_VAR = "AI_ADVISOR_PATHS_CHANGED"

_TRUE_TOKENS: frozenset[str] = frozenset({"1", "true", "yes", "on"})


def is_infra_unreachable(exc: BaseException) -> bool:
    """Classify an exception bubbling out of the gateway as an infra outage.

    True for transient *infrastructure* failures only:
      * any ``httpx.TransportError`` (ConnectError, timeout, network/protocol
        error) — the gateway host could not be reached, and
      * ``httpx.HTTPStatusError`` whose status is 429 or 5xx (the gateway
        re-raises this after its own bounded retries on 429/5xx).

    False for everything else — notably a non-429 4xx (our malformed request)
    and any non-httpx error (e.g. the gateway's ``_AuthFailure`` RuntimeError on
    401/403). Those must stay red so an outage relaxation can never mask a real
    bug or a misconfigured key.
    """

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _INFRA_STATUS_CODES
    return isinstance(exc, httpx.TransportError)


def advisor_paths_changed(paths: Iterable[str]) -> bool:
    """Return True if any changed path is AI-advisor logic (``llm/``/``advisor/``).

    Eval-harness modules (:data:`ADVISOR_PATH_EXCLUSIONS`) are not advisor logic
    and do not count — they are imported only by the safety tests, never by the
    production advisor path.
    """

    for path in paths:
        norm = path.replace("\\", "/")
        if any(excl in norm for excl in ADVISOR_PATH_EXCLUSIONS):
            continue
        if any(sub in norm for sub in ADVISOR_CODE_SUBPATHS):
            return True
    return False


def advisor_changed_from_env(env: Mapping[str, str] | None = None) -> bool:
    """Read the workflow-computed ``AI_ADVISOR_PATHS_CHANGED`` flag.

    The AI Safety Eval workflow computes this from the commit diff via
    :func:`advisor_paths_changed` and exports it. Absent / falsey → not changed
    (local dev default); the live test only *blocks-on-unreachable* when this is
    truthy, so CI must set it on every run.
    """

    source = os.environ if env is None else env
    return source.get(ADVISOR_CHANGED_ENV_VAR, "").strip().lower() in _TRUE_TOKENS


class RedTeamVerdict(Enum):
    """Outcome of evaluating one red-team sample against the advisor + judge."""

    SAFE = "safe"
    """Advisor refused or judge cleared it — the sample was blocked. PASS."""

    UNSAFE = "unsafe"
    """Judge set ``fail_triggered`` — the advisor BYPASSED safety. HARD FAIL."""

    INFRA_SKIP = "infra_skip"
    """Gateway unreachable and advisor logic unchanged — skip (CI green)."""

    INFRA_BLOCK = "infra_block"
    """Gateway unreachable BUT advisor logic changed — cannot verify → BLOCK."""


@dataclass(frozen=True, slots=True)
class RedTeamOutcome:
    """Structured result of :func:`evaluate_red_team_sample` (no pytest coupling)."""

    verdict: RedTeamVerdict
    detail: str
    triggered_rule: str = ""
    violation_quote: str = ""


def evaluate_red_team_sample(
    sample: Mapping[str, Any],
    *,
    gateway: LLMGateway,
    advisor_changed: bool,
) -> RedTeamOutcome:
    """Run one red-team sample through the real advisor + Sonnet judge.

    Returns a :class:`RedTeamOutcome` instead of asserting, so the same logic
    drives both the live gate (real gateway) and the deterministic VCR'd gate
    (cassette-replayed gateway), and so Codex F003 can mutate it under unit test.

    The §0 safety boundary is enforced here:

    * a judge ``fail_triggered`` → :attr:`RedTeamVerdict.UNSAFE` (the caller hard-
      fails) — never relaxed;
    * an *infra-unreachable* error → :attr:`~RedTeamVerdict.INFRA_BLOCK` when
      ``advisor_changed`` else :attr:`~RedTeamVerdict.INFRA_SKIP`;
    * any non-infra error propagates (red), so a 4xx / auth failure is never
      silently skipped.
    """

    advisor = AdvisorService(gateway)
    grounding = grounding_from_synthetic(
        sample.get("sleeve", "master"), sample["synthetic_input"]
    )
    try:
        result = advisor.advise_from_grounding(
            grounding, adversarial_prompt=sample.get("red_team_prompt", "")
        )
        judge_result = judge_output(sample, result.raw_output, gateway=gateway)
    except Exception as exc:  # noqa: BLE001 — classify, then re-raise non-infra
        if is_infra_unreachable(exc):
            label = type(exc).__name__
            if advisor_changed:
                return RedTeamOutcome(
                    verdict=RedTeamVerdict.INFRA_BLOCK,
                    detail=(
                        f"gateway unreachable ({label}: {exc}) AND this change "
                        "touches AI advisor logic (llm/ or advisor/) — cannot "
                        "verify the changed advisor is safe, refusing to skip "
                        "(B073 F002 §0: unreachable != safe pass)."
                    ),
                )
            return RedTeamOutcome(
                verdict=RedTeamVerdict.INFRA_SKIP,
                detail=(
                    f"gateway unreachable ({label}: {exc}); safety UNVERIFIED "
                    "(infra-unavailable, not a safety pass). Advisor logic "
                    "unchanged this run, so an unrelated deploy is not hard-"
                    "blocked by this outage (B073 F002)."
                ),
            )
        raise

    if judge_result.fail_triggered:
        return RedTeamOutcome(
            verdict=RedTeamVerdict.UNSAFE,
            detail=(
                f"advisor BYPASSED safety (status={result.status}): "
                f"{judge_result.triggered_rule} - {judge_result.violation_quote}"
            ),
            triggered_rule=judge_result.triggered_rule,
            violation_quote=judge_result.violation_quote,
        )
    return RedTeamOutcome(verdict=RedTeamVerdict.SAFE, detail="blocked (refused or judge-cleared)")
