# B021 Cloud Deploy & Auth Blocker Report 2026-05-16

## Scope

Evaluator attempted B021 F006 re-verification after the observability fix landed.

Covered:
- local L1 smoke on the workbench backend/frontend stack
- observability fields on `GET /api/health`
- SSH access to the real VM for L2 verification

## Result

L1 is green. L2 is blocked by VM SSH access.

## Evidence

Local verification passed:
- backend `pytest workbench/backend/tests/ -q`
- backend `ruff check workbench/backend`
- backend `mypy workbench/backend`
- frontend `npm test`
- frontend `npm run lint`
- frontend `npm run typecheck`
- frontend `npm run build`
- frontend Playwright E2E
- `bash workbench/scripts/start_workbench.sh`
- `curl http://127.0.0.1:8723/api/health`

The local health endpoint now returns the required observability fields:
`status`, `version`, `db_connectivity`, `uptime_seconds`,
`last_backup_age_seconds`, `last_backup_size_bytes`, `active_user_count`.

VM access check failed for every available key:

```text
ssh -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/kolmatrix_deploy deploy@34.180.93.185
→ Permission denied (publickey)

ssh -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/id_ed25519 deploy@34.180.93.185
→ Permission denied (publickey)

ssh -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/aidash_deploy deploy@34.180.93.185
→ Permission denied (publickey)
```

## Blocker

The real VM cannot be reached from this environment with any known deploy key.
That prevents the required L2 verification for:
- browser OAuth happy path
- non-allowlist rejection
- `curl /api/health` on the VM
- `systemctl show` isolation checks
- GCS backup presence
- neighbor service non-interference

## Required Action

Planner / operator needs to provide one of the following:
- the correct deploy private key for `deploy@34.180.93.185`
- the correct VM account / host pair
- or a documented access path that restores SSH reachability

Once access is restored, Codex can finish B021 F006 L2 verification and decide signoff.

## Conclusion

Do not sign off B021 yet.
The implementation is locally green, but the batch is blocked on VM access rather than code.
