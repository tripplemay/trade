# B022 Workbench Phase 1 Reverification Round 3 2026-05-18

## Scope

Codex reverified B022 F014 after fixing-round 3 on the production deployment
at `https://trade.guangai.ai` using the existing authenticated Chrome
remote-debugging session.

Covered:
- local backend regression tests for the fixing-round 3 snapshots / backlog /
  error-buffer changes
- authenticated production API probes for auth, health, snapshots, backlog,
  recommendations export, and recent-errors
- authenticated production browser walkthrough for Snapshots, Backlog, and
  Recommendations export

Not covered:
- production host `journalctl` inspection, because SSH is still closed from the
  current Codex environment
- final signoff, because blocking production failures remain

## Result

FAIL. Round-3 recovered the Snapshots list read path and unlocked a new
diagnostic surface, but B022 still cannot be signed off.

The production deployment now returns `200 {"snapshots":[]}` for
`GET /api/snapshots`, and the authenticated `/snapshots` page renders its empty
state instead of `HTTP 500`. The Recommendations page export button is also now
fully working end-to-end in the browser. However, Backlog create still fails,
and the Snapshots refresh flow still ends in an error modal.

## Passing Evidence

### Local regression

- `.venv/bin/python -m pytest workbench/backend/tests/unit/test_db_degrade.py workbench/backend/tests/unit/test_backlog_prod_config.py workbench/backend/tests/unit/test_error_buffer.py workbench/backend/tests/unit/test_snapshots.py`
  -> `14 passed`
- `.venv/bin/python -m ruff check ...` on the touched backend files -> pass
- `.venv/bin/python -m mypy ...` on the touched backend files -> pass

### Authenticated production session

- `GET /api/auth/session` -> `200` with allowlisted user
  `tripplezhou@gmail.com`
- `GET /api/protected-test` -> `200`
- `GET /api/health` -> `200`
- Production `/api/health.version` ->
  `6c0d282420d72339d31f2918fefe2348ff062bfa`
- Local `git rev-parse HEAD` ->
  `6c0d282420d72339d31f2918fefe2348ff062bfa`

### Recovered production surfaces

- `GET /api/snapshots` -> `200 {"snapshots":[]}`
- `/snapshots` page renders `0 snapshots` empty state instead of `HTTP 500`
- `GET /api/debug/recent-errors` -> `200 {"count":0,"records":[]}` before the
  failing write-path probes
- Recommendations page browser flow now passes end-to-end:
  - export button visible and enabled
  - click succeeds
  - page renders `Wrote /var/lib/workbench/runs/2026-05-18/order-ticket-2026-05-18.md`

## Blocking Findings

| ID | Severity | Finding | Evidence | Required Fix |
|---|---|---|---|---|
| B022-F012-3 | high | Production Backlog create still fails. The new `/api/debug/recent-errors` surface shows this is not the old git-working-tree issue anymore; the route now fails earlier on a missing database table. | Authenticated `POST /api/backlog` -> `500 {"detail":"Internal Server Error"}`. `GET /api/debug/recent-errors` then records `OperationalError: no such table: backlog_entry` on path `/api/backlog`. | Fix production schema / migration state so `backlog_entry` exists, then re-run authenticated Backlog create/edit/delete. |
| B022-F011-3 | high | Production Snapshots refresh still fails even though the list page now degrades correctly. The refresh modal reaches `ERROR` because the backing table is missing. | Browser refresh flow showed modal phases through `PREPARE/FETCH/PROCESS/STORE` and then `ERROR`. `GET /api/debug/recent-errors` records `OperationalError: no such table: snapshot_meta` on path `/api/snapshots/refresh`. | Fix production schema / migration state so `snapshot_meta` exists, then re-run refresh and verify the expected successful completion path. |
| B022-F014-OBS2 | medium | SSHless diagnosis is no longer a blocker because `/api/debug/recent-errors` works, but direct VM log inspection is still unavailable from Codex. | `GET /api/debug/recent-errors` returned the exact `OperationalError` records above. SSH is still closed, so no `journalctl` confirmation was possible. | Generator can work from the API-exposed exceptions directly, or the operator can still provide `journalctl` if deeper context is needed. |

## Conclusion

B022 remains in `fixing`.

Round-3 proved that the remaining failures are now narrowed to concrete
production schema gaps:

1. missing `backlog_entry`
2. missing `snapshot_meta`

Until those tables exist in production, Codex cannot sign off B022.
