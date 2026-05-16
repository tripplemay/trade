# B021 Cloud Deploy & Auth Verification Blocker Report 2026-05-16

## Scope

Evaluator attempted B021 F006 re-verification after the observability fix landed.

Covered:
- local L1 smoke on the workbench backend/frontend stack
- observability fields on `GET /api/health`
- public read-only L2 checks against `https://trade.guangai.ai`
- route discovery for the OAuth flow

## Result

L1 is green. Public L2 checks now show one remaining gap:
- `https://trade.guangai.ai/api/auth/signin/google` responds with `error=Configuration`, so OAuth cannot complete even though the route is now reachable.

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
- browser OAuth happy path cannot complete because the sign-in endpoint returns a configuration error
- non-allowlist rejection cannot be exercised until sign-in succeeds

The rest of the public health fields are present and healthy:
- `status=ok`
- `version` now matches the deployed release SHA
- `db_connectivity=ok`
- `uptime_seconds` present
- `last_backup_age_seconds` present
- `last_backup_size_bytes` present
- `active_user_count` present

## Required Action

Required fix path:
- verify the production frontend has a valid Auth.js runtime configuration on the VM:
  - `GOOGLE_OAUTH_CLIENT_ID`
  - `GOOGLE_OAUTH_CLIENT_SECRET`
  - `NEXTAUTH_SECRET`
  - `NEXTAUTH_URL=https://trade.guangai.ai`
  - `ALLOWED_USER_EMAIL`
- restart the frontend service after syncing the env/config if needed
- then rerun browser OAuth happy path and non-allowlist rejection checks

## Conclusion

Do not sign off B021 yet.
The implementation is locally green, but production still fails the Auth.js runtime configuration requirement.
