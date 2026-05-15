# B021 Cloud Deploy & Auth Verification Blocker Report 2026-05-16

## Scope

Evaluator attempted B021 F006 re-verification after the observability fix landed.

Covered:
- local L1 smoke on the workbench backend/frontend stack
- observability fields on `GET /api/health`
- public read-only L2 checks against `https://trade.guangai.ai`
- route discovery for the OAuth flow

## Result

L1 is green. Public L2 checks show two remaining gaps:
- `version` on `GET /api/health` is `dev`, not the current `git rev-parse --short HEAD`
- `https://trade.guangai.ai/api/auth/*` returns 404, so the OAuth path is not reachable through the production proxy

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

Historical SSH access check from the earlier attempt also failed for every available key:

```text
ssh -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/kolmatrix_deploy deploy@34.180.93.185
→ Permission denied (publickey)

ssh -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/id_ed25519 deploy@34.180.93.185
→ Permission denied (publickey)

ssh -o BatchMode=yes -o ConnectTimeout=10 -i ~/.ssh/aidash_deploy deploy@34.180.93.185
→ Permission denied (publickey)
```

## Blocker

The current public evidence is enough to block signoff:
- browser OAuth happy path cannot start because `/api/auth` is 404
- non-allowlist rejection cannot be exercised without a reachable auth endpoint
- `version=dev` does not satisfy the spec's `git rev-parse HEAD` check

The rest of the public health fields are present and healthy:
- `status=ok`
- `db_connectivity=ok`
- `uptime_seconds` present
- `last_backup_age_seconds` present
- `last_backup_size_bytes` present
- `active_user_count` present

## Required Action

Required fix path:
- route `/api/auth/*` to the NextAuth handler in the frontend, or otherwise make the auth handler reachable on the production host
- inject the real release SHA into the deployed backend so `/api/health` reports the commit instead of `dev`
- then rerun browser OAuth happy path and non-allowlist rejection checks

## Conclusion

Do not sign off B021 yet.
The implementation is locally green, but production still fails the auth-route and version-field requirements.
