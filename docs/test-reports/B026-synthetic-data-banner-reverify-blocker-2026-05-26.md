# B026 Synthetic Data Banner Reverify Blocker — 2026-05-26

## Scope
- Batch: `B026-synthetic-data-banner`
- Sprint: `F002`
- Evaluator phase: `reverifying`
- Local HEAD: `c9274b5ba18146e132de5a5061556d020af73066`

## Verdict
- `L1 PASS`
- `L2 FAIL`
- `SIGNOFF BLOCKED`

## What Changed From The First Round
- Generator's clean-env hypothesis was valid for the previous local failures.
- After `rm -rf .next node_modules && npm ci`, the earlier L1 blockers no longer reproduced.
- Local `npm run build` succeeded, including `/execution/journal-history` and `/execution/position-diff`.
- Local Playwright also recovered and passed fully.

## L1 Evidence
- Backend: `pytest 241 passed, 2 skipped`, `ruff`, `mypy` all green.
- Trade: `pytest 727 passed`, `mypy` green.
- Frontend: `lint`, `typecheck`, `vitest 165 passed`, `build`, `npm audit --omit=dev --audit-level=high` all green.
- Playwright inventory: `38 tests in 6 files`.
- Playwright execution: `38 passed`.
- Anonymous `/login` and `/ -> /login` no longer rendered `Internal Server Error`.

## L2 Blocker
- Production hash equivalence was healthy at reverify time: `/api/health.version == c9274b5ba18146e132de5a5061556d020af73066`.
- Production read-only locale checks were green for zh-CN and en across home, strategies, reports, and report detail.
- `/api/debug/recent-errors` returned `200 {"count":0,"records":[]}`.
- The remaining hard blocker is banner dismiss behavior on production:
  - Before click: `data-testid="synthetic-data-banner"` count `1`, visible `true`
  - After clicking `data-testid="synthetic-data-banner-close"`: count still `1`, visible still `true`
  - After reload: count `1`, visible `true`
- Acceptance requires: close should hide the banner in the current session view, and reload should make it appear again.
- Actual behavior only satisfies the reload half; the pre-reload hide requirement fails.

## Reproduction
1. Open production protected page with banner visible, for example `https://trade.guangai.ai/strategies`.
2. Confirm `data-testid="synthetic-data-banner"` is visible.
3. Click `data-testid="synthetic-data-banner-close"`.
4. Observe banner remains visible on the same page.
5. Reload page.
6. Observe banner remains visible, which is acceptable only after a successful hide in step 4.

## Impact
- The batch cannot be signed off because the user-facing dismiss interaction does not work as specified in production.
- This is a real runtime product defect, not a local-environment false positive.

## Test Artifacts
- Screenshots saved under `docs/screenshots/B026-banner/`
- zh-CN:
  - `home.png`
  - `reports.png`
- en:
  - `home.png`
  - `strategies.png`

## Next Action For Generator
- Fix the dismiss interaction so the close button hides the banner immediately in the current rendered page/session.
- Preserve the intended reload behavior: banner should appear again after full page reload while the env flag remains enabled.
