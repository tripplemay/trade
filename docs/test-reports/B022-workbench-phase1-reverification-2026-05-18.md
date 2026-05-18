# B022 Workbench Phase 1 Reverification 2026-05-18

## Scope

Codex reverified B022 F014 after fixing-round 2 on the production deployment
at `https://trade.guangai.ai` using an authenticated Chrome remote-debugging
session.

Covered:
- local backend regression tests for the fixing-round 2 DB-degrade + Snapshots
  changes
- authenticated production API probes for dashboard / recommendations /
  snapshots / backlog
- authenticated production browser walkthrough for Home / Recommendations /
  Snapshots / Backlog
- production Reports detail rendering for B019 heavy-table AG Grid swap
- production Backtest run trigger

Not covered:
- production host `journalctl` root-cause inspection, because SSH from the
  current Codex environment to the VM was closed
- final signoff, because blocking production failures remain

## Result

FAIL. OAuth and the authenticated browser path are now available, but B022
still cannot be signed off.

The round-2 deploy fixed three previously-blocking authenticated read paths:
Dashboard, Recommendations, and Backlog list now return non-500 responses and
render usable empty states. However, the Snapshots read path still returns
`500`, and Backlog create still fails with `500`.

## Passing Evidence

### Local regression

- `.venv/bin/python -m pytest workbench/backend/tests/unit/test_db_degrade.py workbench/backend/tests/unit/test_snapshots.py`
  -> `7 passed`
- `.venv/bin/python -m ruff check ...` on the touched backend files -> pass
- `.venv/bin/python -m mypy ...` on the touched backend files -> pass

### Authenticated production session

- `GET /api/auth/session` -> `200` with allowlisted user
  `tripplezhou@gmail.com`
- `GET /api/protected-test` -> `200`
- `GET /api/health` -> `200`
- Production `/api/health.version` ->
  `e64a555371693c8bd77da2e0cd019c72e9a31699`
- Local `git rev-parse HEAD` ->
  `e64a555371693c8bd77da2e0cd019c72e9a31699`

### Production pages / APIs now recovered

- `GET /api/dashboard` -> `200`
- Home page state -> `live`
- Home page renders zeroed cards plus recent reports instead of `HTTP 500`
- `GET /api/recommendations/current` -> `200`
- Recommendations page renders `account missing` empty state instead of
  `HTTP 500`
- `GET /api/backlog` -> `200`
- Backlog page renders `0 entries (showing 0)` instead of `HTTP 500`

### Previously-passing L2 items still pass

- Strategies page renders `4 sleeves`
- Reports page renders `50 reports`
- `B019-retune-sweep` detail page renders heavy markdown tables via AG Grid
  (`markdown-heavy-table` count = `4`)
- Backtest run still succeeds from the authenticated browser:
  state changed `idle` -> `run f93c1052cd0e` in ~`1579 ms`

### Recommendations export API recovered

Direct authenticated API probe:

```json
{
  "path": "/var/lib/workbench/runs/2026-05-18/order-ticket-2026-05-18.md",
  "disclaimer": "research-only; this is a manual review checklist, not a trading instruction"
}
```

This satisfies the required disclaimer literal on the backend response surface.

## Blocking Findings

| ID | Severity | Finding | Evidence | Required Fix |
|---|---|---|---|---|
| B022-F011-2 | high | Production Snapshots read path still fails. `GET /api/snapshots` returns `500`, so the authenticated `/snapshots` page still shows `unreachable: HTTP 500`. | Authenticated probe: `/api/snapshots` -> `500 {"detail":"Internal Server Error"}`. Browser page state: `unreachable: HTTP 500`. | Inspect production backend logs for the exact exception on `/api/snapshots`, fix the remaining read-path failure, then re-run browser refresh and verify the 5 SSE stages complete. |
| B022-F012-2 | high | Production Backlog write path still fails even though the list path now degrades to a safe empty state. | Authenticated browser create attempt returned toast text `Submit failed: HTTP 500: {"detail":"Internal Server Error"}`. `GET /api/backlog` remained `200 {"entries":[]}` afterward. | Inspect production backend logs for the exact exception during Backlog POST, fix the mutation path, then re-run create/edit/delete and verify the expected `chore(backlog): add|edit|delete BL-WB-XXXX` commit behavior. |
| B022-F010-2 | medium | Recommendations backend export works, but full page-level export interaction was not counted as PASS in this round because the page probe hit a transient loading/disabled state before the final API-only confirmation. | The page snapshot showed `state: loading…` and `exportDisabled: true`, while the direct authenticated POST to `/api/recommendations/export-ticket` succeeded with the required path + disclaimer. | After the remaining production blockers are fixed, re-run the page-level export button flow once more and confirm the UI shows a successful `recommendations-export-result`. |
| B022-F014-OBS | medium | Codex still could not inspect production `journalctl`, so the current report can only prove the failing surfaces, not the exact root cause on the VM. | SSH probe to `trade.guangai.ai:22` from the current Codex environment returned `Connection closed by 198.18.1.39 port 22`. | Have the operator provide recent `journalctl -u workbench-backend.service -n 200 --no-pager` output or reopen the read-only SSH path so the remaining 500s can be tied to concrete exceptions. |

## Required Action

Generator should address the remaining production blockers before Codex runs a
final reverification:

1. Fix `/api/snapshots` read-path `500` in production.
2. Fix Backlog POST mutation `500` in production.
3. Provide production backend log evidence for the above failures.
4. Re-run the Recommendations export UI path once the remaining blockers are
   cleared.

## Conclusion

B022 remains in `fixing`.

Authenticated browser access is no longer the blocker. The batch is now
blocked by two concrete production backend failures: Snapshots read and
Backlog write.
