# Branch Protection Guidance for `main`

Status: B071 F001 refresh (門禁确权 — added the safety-eval gate to the
required list, corrected the check-run names to job contexts, + pinned
path-scoped "required" semantics; originally B020 guidance, B022 Phase 1
refresh). See the full audit at `docs/dev/B071-gate-authority-audit.md`.

This document records the manual GitHub branch-protection settings the
user should apply for `main`. It is intentionally advisory only; Codex
does not change repository settings.

> **What is already enforced without any ruleset (B071 F001 audit):**
> this project's normal flow is **direct push to `main`** (see
> `harness-rules.md` §分支规则), not PR-merge. The *real* automated gate
> today is the **push-to-`main` CI** (the four CI workflows below) plus
> **`workbench-deploy`'s `conclusion=='success'` re-check** — a red CI or
> red AI Safety Eval short-circuits the deploy's `if:` and never
> publishes. The branch-protection ruleset described here is a *second,
> currently-advisory* PR-merge gate that only bites once the team adopts
> a PR workflow.

## Required protections

1. Require status checks before merge. **Select the check-run name (=
   job name), not the workflow display name** — GitHub's selector lists
   the job's check-run name, and these jobs carry no `name:`, so the
   string to pick is the job key (B071 F001 audit §4):
   - `python-checks` *(job in `python-ci.yml` — NOT `python-ci`)*
   - `workbench-backend`
   - `workbench-frontend`
   - **`safety-eval` (B071 F001 addition — job in `ai-safety-eval.yml`,
     NOT `AI Safety Eval`)** — the red-team safety
     gate (`ai-safety-eval.yml`, 15 samples + workflow-wiring
     assertions). It runs on push/PR touching the LLM module, advisor,
     red-team dataset, or its own yml, **and** is the third upstream
     deploy gate in `workbench-deploy.yml` (permanent boundary (n): a
     red safety eval must block production). Previously missing from
     this list — corrected in B071 F001.
   - **`workbench-deploy` (B022 F013 addition — candidate)** — the
     workflow runs on `workflow_run` after any upstream CI succeeds;
     treat it as a required-status-check candidate only after confirming
     GH surfaces `workflow_run` checks as enforceable. If not, leave it
     advisory; the deploy step always rolls back on a healthcheck
     failure so a green CI + bad runtime never publishes.
2. Require linear history.
3. Block force pushes to `main`.
4. Optionally require 1 approving review if the team wants review-gated
   merges.

## Why these checks exist

- `python-ci` protects the existing `trade/` stdlib code path.
- `workbench-backend` protects the FastAPI scaffold, safety guards, and
  backend type / lint / unit checks.
- `workbench-frontend` protects the Next.js scaffold, OpenAPI drift
  check, Vitest, and Playwright smoke coverage (anon + authed projects).
- `AI Safety Eval` (B032 F002) runs the red-team prompt-injection /
  no-AI-prediction gate against the real advisor and pins the
  workflow-wiring invariants. It is **also** a deploy gate — listed
  among `workbench-deploy.yml`'s upstream `workflow_run` workflows so a
  red run blocks production (permanent boundary (n)).
- `workbench-deploy` (B022 F013) is the actual production publish step
  + post-deploy healthcheck + automatic rollback. Adding it to required
  checks blocks merges whose deploy can't reach `https://trade.guangai.ai`.
- Linear history keeps the batch handoff trail easy to audit.

## Notes

- The workbench workflows are path-scoped, so the checks only run when
  relevant files change.
- **★ Path-scoped + "required" gotcha (B071 F001).** All four CI gates
  are path-scoped (`python-ci` via `paths-ignore`; the rest via `paths`
  include). If you mark a path-scoped check **required** and a PR does
  **not** touch its matching paths, that workflow never triggers, the
  required check never reports, and the PR sticks on "Expected —
  Waiting for status to be reported" and **cannot merge**. A purely
  front-end PR, for example, never triggers `python-ci` /
  `workbench-backend`. Mitigations if you adopt PR gating: (a) add one
  "always-run aggregate gate" job as the single required check that
  internally waits on the path-relevant workflows, or (b) confirm your
  current GitHub version treats a not-triggered required check as
  *skipped → not blocking* before naming all four CIs as required.
  Because this project pushes directly to `main` (not PR-merge), this
  gotcha is currently dormant — but document it before flipping on
  required checks.
- The `trade/` CI pipeline remains separate from the workbench
  pipelines.
- If a new workbench workflow is added later, add its status check here
  before enabling merge protection.
- `workbench-deploy.yml` runs on `workflow_run`, not `push` — GitHub
  sometimes lists such checks as advisory rather than enforceable.
  Verify the check appears under "required status checks" in repo
  settings before relying on it.

## Manual verification

Before enabling protection, confirm the following GitHub settings:

- `main` is the default branch.
- Branch protection applies to `main` only.
- Merge commits are disallowed if linear history is required.
- Force-push bypass is disabled for all roles.

