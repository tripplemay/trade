# B026 Synthetic Data Banner Blocker 2026-05-25

## Scope
- F002 first-round verification
- L1 local verification for B026 F001
- L2 production verification not entered because L1 failed

## Result
- `L1 FAIL`
- `L2 NOT RUN`

## Evidence

### Production hash gate is currently healthy
- `git rev-parse HEAD` → `c9274b5ba18146e132de5a5061556d020af73066`
- `curl -sS https://trade.guangai.ai/api/health`
- Response `version` = `c9274b5ba18146e132de5a5061556d020af73066`

### Green gates
- backend: `pytest tests -q` → `241 passed, 2 skipped`
- backend: `ruff check .` → pass
- backend: `mypy workbench_api tests` → pass
- trade: `pytest tests -q` → `727 passed`
- trade: `mypy trade` → pass
- frontend: `npm run lint` → pass
- frontend: `npm run typecheck` → pass
- frontend: `npm test` → `165 passed`
- frontend: `npm audit --omit=dev --audit-level=high` → exit 0 with only `moderate` advisories
- artifact grep on `.next/static` → no forbidden localhost backend host
- `npx playwright test --list` → `Total: 38 tests in 6 files`

### Hard blocker 1: `next build` is red
- Command:
  - `cd workbench/frontend && npm run build`
- Failure:
  - `PageNotFoundError: Cannot find module for page: /execution/journal-history`
  - `PageNotFoundError: Cannot find module for page: /execution/position-diff`
  - `Build error occurred`
  - `Failed to collect page data for /execution/journal-history`
- Relevant files do exist:
  - `src/app/(protected)/execution/journal-history/page.tsx`
  - `src/app/(protected)/execution/position-diff/page.tsx`
- So this is not a missing-file typo at the filesystem level; the module is failing during Next build/page-data collection.

### Hard blocker 2: Playwright runtime is broadly broken
- Command:
  - `cd workbench/frontend && NEXTAUTH_SECRET=codex-local-test-secret ALLOWED_USER_EMAIL=codex@example.com npx playwright test`
- Failures started on anonymous entry pages:
  - `tests/safety/disclaimer-present.spec.ts` `/login`
  - `tests/e2e/home-loads.spec.ts` `/ -> /login`
- Both error contexts show page content:
  - `Internal Server Error`
- Example evidence:
  - `test-results/safety-disclaimer-present-disclaimer-visible-on-login-anon/error-context.md`
  - `test-results/e2e-home-loads-workbench-e-1a691-and-surfaces-the-disclaimer-anon/error-context.md`
- Failure then propagates to protected routes and the new B026 banner suite:
  - `tests/e2e/protected-routes.spec.ts` cannot find `workbench-topbar`
  - `tests/e2e/b026-synthetic-banner.spec.ts` cannot find `synthetic-data-banner`
- Example protected-route evidence:
  - `test-results/e2e-protected-routes-shell-disclaimer-render-on-strategies-authed/error-context.md`
  - body text again shows `Internal Server Error`
- Example B026 evidence:
  - `test-results/e2e-b026-synthetic-banner--f3be0-h-CN-headline-on-strategies-authed/error-context.md`
  - body text again shows `Internal Server Error`

## Required Action
- Generator needs to fix the frontend runtime/build regression before Codex can continue.
- Minimum re-entry bar:
  - `npm run build` green
  - anonymous `/login` renders normally again
  - `npx playwright test` no longer collapses into `Internal Server Error` on base routes

## Conclusion
- Do **not** sign off B026 F002 in this round.
- This is a real L1 blocker, not a production deploy drift issue.
