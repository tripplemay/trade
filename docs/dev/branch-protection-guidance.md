# Branch Protection Guidance for `main`

Status: B022 Phase 1 refresh (originally B020 guidance).

This document records the manual GitHub branch-protection settings the
user should apply for `main`. It is intentionally advisory only; Codex
does not change repository settings.

## Required protections

1. Require status checks before merge:
   - `python-ci`
   - `workbench-backend`
   - `workbench-frontend`
   - **`workbench-deploy` (B022 F013 addition — candidate)** — the
     workflow runs on `workflow_run` after either CI succeeds; treat
     it as a required-status-check candidate only after confirming GH
     surfaces `workflow_run` checks as enforceable. If not, leave it
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
- `workbench-deploy` (B022 F013) is the actual production publish step
  + post-deploy healthcheck + automatic rollback. Adding it to required
  checks blocks merges whose deploy can't reach `https://trade.guangai.ai`.
- Linear history keeps the batch handoff trail easy to audit.

## Notes

- The workbench workflows are path-scoped, so the checks only run when
  relevant files change.
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

