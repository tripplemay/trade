# B020 Dev Infrastructure Review 2026-05-15

## Scope

Evaluator performed F005 independent L1 verification for B020 Dev Infrastructure.

Reviewed areas:
- B020 spec and feature acceptance.
- `workbench/backend` scaffold, safety guards, and `/health` contract.
- `workbench/frontend` scaffold, disclaimer rendering, generated types, and browser smoke path.
- CI workflow shape, OpenAPI drift pipeline, and branch-protection guidance.
- Fixture-first and no-live/no-secret/no-network/no-broker/no-paper safety boundaries.

## Result

FAIL. One blocking acceptance gap remains.

## Findings

| ID | Severity | Finding | Evidence | Required Fix |
|---|---|---|---|---|
| B020-F005-1 | high | `workbench/scripts/start_workbench.sh` is not portable on the current host. The script uses `wait -n`, but the machine’s default `/bin/bash` is 3.2.57, which does not support `wait -n`. As a result, the required zero-to-running boot command exits with `wait: -n: invalid option`. This blocks Acceptance 1 and prevents a full signoff. | Local run: `bash workbench/scripts/start_workbench.sh` printed backend/frontend startup URLs and then exited with `wait: -n: invalid option`; exit code 2. Host shell check: `/bin/bash` is GNU bash 3.2.57. | Replace the `wait -n` usage with a portable loop / trap pattern, or explicitly require a newer Bash and document that prerequisite in `workbench/README.md` so the boot command works from a fresh clone. |

## Passing Evidence

Commands executed:

```text
.venv/bin/python -m pytest workbench/backend/tests/ -q
7 passed in 0.55s

.venv/bin/python -m ruff check workbench/backend
All checks passed!

.venv/bin/python -m mypy workbench/backend
Success: no issues found in 10 source files

cd workbench/frontend && npm run lint
PASS

cd workbench/frontend && npm run typecheck
PASS

cd workbench/frontend && npm test
5 passed

cd workbench/frontend && PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright npm run test:e2e -- --reporter=list
2 passed (2.2s)

cd workbench/frontend && PYTHON_BIN=/Users/yixingzhou/project/trade/.venv/bin/python \
  PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright \
  bash scripts/generate-types.sh && git diff --exit-code src/types/api.ts
PASS (no drift in main workspace)

git diff --check
PASS
```

## Trip-Test Evidence

All requested boundary-violation checks failed closed in a temporary worktree:

```text
backend broker import trip:
.venv/bin/python -m pytest /tmp/.../workbench/backend/tests/safety/test_no_broker_sdk_imports.py -q
1 failed

backend paper/live URL trip:
.venv/bin/python -m pytest /tmp/.../workbench/backend/tests/safety/test_no_paper_or_live_urls.py -q
1 failed

backend settings allowlist trip:
.venv/bin/python -m pytest /tmp/.../workbench/backend/tests/safety/test_settings_env_allowlist.py -q
1 failed, 1 passed

frontend broker import trip:
/Users/yixingzhou/project/trade/workbench/frontend/node_modules/.bin/vitest run tests/safety/no-broker-sdk-imports.spec.ts
1 failed, 1 passed

frontend disclaimer trip:
PLAYWRIGHT_BASE_URL=http://127.0.0.1:3001 \
  /Users/yixingzhou/project/trade/workbench/frontend/node_modules/.bin/playwright test \
  tests/safety/disclaimer-present.spec.ts --reporter=list
1 failed

OpenAPI drift trip:
cd /tmp/.../workbench/frontend && PYTHON_BIN=/Users/yixingzhou/project/trade/.venv/bin/python \
  bash scripts/generate-types.sh && git diff --exit-code src/types/api.ts
exit code 1; generated `src/types/api.ts` differed after adding `build: string` to the temporary `/health` schema
```

## Acceptance Assessment

| Feature | Result | Notes |
|---|---|---|
| F001 Workbench skeleton + toolchain bootstrap | PASS | Backend and frontend scaffolds exist and pass local lint/type/test checks. |
| F002 CI workflows | PASS | Backend and frontend workflow files are present; path-scoped isolation is in place. |
| F003 Testing strategy + safety guard scaffolding | PASS | Strategy doc and five boundary guards exist; trip-tests confirmed the guards fail closed. |
| F004 OpenAPI ↔ TypeScript pipeline + drift check | PASS | Generator works and drift detection is wired into the workflow. |
| F005 Independent evaluation | FAIL | Boot command portability issue blocks full signoff. |

## Non-Blocking Notes

| ID | Note | Risk | Follow-up |
|---|---|---|---|
| N1 | The Playwright browser cache on this machine required downloading the matching Chromium build `1140`; after that, the E2E smoke passed. | low | CI already provisions browsers, so this is a local-host setup concern only. |
| N2 | The temporary worktree used for trip-tests contained intentional violations only and was not committed. | low | No repository change required. |

## Conclusion

B020 is close, but it should not be signed off yet. Fix the boot script portability issue first, then rerun the zero-to-running check and sign off only after the boot command succeeds from the documented shell environment.
