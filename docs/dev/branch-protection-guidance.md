# Branch Protection Guidance for `main`

Status: B020 dev-infrastructure guidance.

This document records the manual GitHub branch-protection settings the
user should apply for `main`. It is intentionally advisory only; Codex
does not change repository settings.

## Required protections

1. Require status checks before merge:
   - `python-ci`
   - `workbench-backend`
   - `workbench-frontend`
2. Require linear history.
3. Block force pushes to `main`.
4. Optionally require 1 approving review if the team wants review-gated
   merges.

## Why these checks exist

- `python-ci` protects the existing `trade/` stdlib code path.
- `workbench-backend` protects the FastAPI scaffold, safety guards, and
  backend type / lint / unit checks.
- `workbench-frontend` protects the Next.js scaffold, OpenAPI drift
  check, Vitest, and Playwright smoke coverage.
- Linear history keeps the batch handoff trail easy to audit.

## Notes

- The workbench workflows are path-scoped, so the checks only run when
  relevant files change.
- The `trade/` CI pipeline remains separate from the workbench
  pipelines.
- If a new workbench workflow is added later, add its status check here
  before enabling merge protection.

## Manual verification

Before enabling protection, confirm the following GitHub settings:

- `main` is the default branch.
- Branch protection applies to `main` only.
- Merge commits are disallowed if linear history is required.
- Force-push bypass is disabled for all roles.

