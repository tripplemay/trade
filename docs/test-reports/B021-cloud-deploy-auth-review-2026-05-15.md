# B021 Cloud Deploy & Auth Review 2026-05-15

## Scope

Evaluator performed F006 independent verification for B021 Cloud Deploy & Auth.

Reviewed areas:
- Google OAuth / NextAuth v5 allowlist flow.
- SQLite + Alembic + repository layer.
- systemd / nginx / certbot deployment artifacts.
- GitHub Actions deploy pipeline.
- Backup automation and restore path.
- Safety guards inherited from B020.
- L1 local smoke, lint, type-check, build, and Playwright E2E.

## Result

FAIL. Two blocking gaps remain before signoff.

## Findings

| ID | Severity | Finding | Evidence | Required Fix |
|---|---|---|---|---|
| B021-F006-1 | high | The observability layer called out in the spec is not implemented. There is no `workbench_api/observability/` package, `/api/health` does not expose the required `uptime_seconds`, `last_backup_age_seconds`, `last_backup_size_bytes`, or `active_user_count` fields, and structured request logging / Sentry gating are absent. | Repository scan found no observability files. `rg` over backend/frontend/deploy found only spec references. Current `/api/health` returns only `status`, `version`, and `db_connectivity`. | Implement the observability package, enrich `/api/health` with the required fields, add JSON logging with `request_id` / `user_id`, and wire the optional Sentry env gate. |
| B021-F006-2 | medium | `mypy workbench/backend` fails on the B021 backend test suite because `workbench/backend/tests/unit/test_health.py` has an untyped `monkeypatch` parameter. This blocks the batch's required type-check green status. | Command: `.venv/bin/python -m mypy workbench/backend` → `workbench/backend/tests/unit/test_health.py:35: error: Function is missing a type annotation for one or more parameters [no-untyped-def]`. | Add the missing annotation in the test file or otherwise adjust the test to satisfy the repository's mypy policy. |

## Passing Evidence

Commands executed:

```text
.venv/bin/python -m pytest workbench/backend/tests/ -q
42 passed in 2.17s

.venv/bin/python -m ruff check workbench/backend
All checks passed!

cd workbench/frontend && npm test
20 passed

cd workbench/frontend && npm run lint
No ESLint warnings or errors

cd workbench/frontend && npm run build
PASS

cd workbench/frontend && PLAYWRIGHT_BROWSERS_PATH=$HOME/Library/Caches/ms-playwright npm run test:e2e
2 passed
```

## Runtime Smoke

```text
bash workbench/scripts/start_workbench.sh
→ backend and frontend started successfully on 127.0.0.1:8723 and 3000

curl http://127.0.0.1:8723/api/health
{"status":"ok","version":"d4aa0c5","db_connectivity":"ok"}

curl http://127.0.0.1:8723/api/protected-test
500
```

The protected route currently fail-closes without auth configuration, which is
acceptable for a missing-secret configuration, but it is not a signoff path.

## Acceptance Assessment

| Feature | Result | Notes |
|---|---|---|
| F001 Google OAuth integration | PASS | Auth callbacks, allowlist behavior, and cookie validation are covered by tests. |
| F002 SQLite + Alembic + Repository layer | PASS | Unit tests and DB round-trips pass. |
| F003 systemd / nginx / certbot deploy artifacts | PASS | Artifact files exist and the local scaffold is coherent. |
| F004 CI/CD deploy pipeline | PASS | Workflow file and rollback path are present. |
| F005 Backup automation | PASS | Backup / restore scripts and timer/service artifacts are present. |
| F006 Observability + signoff | FAIL | Observability is missing and mypy is red. |

## Non-Blocking Notes

| ID | Note | Risk | Follow-up |
|---|---|---|---|
| N1 | The frontend auth tests and the production callback safety regression are green. | low | Keep these in the CI gate. |
| N2 | `start_workbench.sh` boot smoke is now green on the local host. | low | Keep the portable boot test in place. |

## Conclusion

B021 should move to fixing. Implement observability and clear the mypy failure,
then rerun L1. L2 on the real VM is not ready until those issues are closed.
