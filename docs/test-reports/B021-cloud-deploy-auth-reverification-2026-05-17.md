# B021 Cloud Deploy & Auth Reverification 2026-05-17

## Scope

Codex reverified B021 F006 on the production host after fix-round 4.

Covered:
- public health endpoint
- Google OAuth browser happy path using the allowlisted account
- authenticated session / protected backend probe
- production home page state after login

## Result

FAIL. OAuth now works, but the authenticated production home page still reports
the backend as unreachable.

## Passing Evidence

### Public health

`GET https://trade.guangai.ai/api/health` returns 200 with all required fields:

```json
{
  "status": "ok",
  "version": "600fc553f1c639f113647d94d178815230aa27ed",
  "db_connectivity": "ok",
  "uptime_seconds": 79380.782,
  "last_backup_age_seconds": 78965.05,
  "last_backup_size_bytes": 114,
  "active_user_count": 0
}
```

### OAuth happy path

Using the Chrome instance exposed on local remote debugging port 9222:

- Opened `https://trade.guangai.ai/login`.
- Clicked the Google sign-in button via Chrome DevTools Protocol.
- Google accepted the existing `tripplezhou@gmail.com` session.
- Browser returned to `https://trade.guangai.ai/`.
- `GET /api/auth/session` returned `tripplezhou@gmail.com`.
- `GET /api/protected-test` returned 200:

```json
{"status":"ok","email":"tripplezhou@gmail.com"}
```

This closes the previous Auth.js false-positive around `GET /api/auth/signin/google`.
The real sign-in path is POST with CSRF, and the browser flow works.

## Blocking Finding

| ID | Severity | Finding | Evidence | Required Fix |
|---|---|---|---|---|
| B021-F006-3 | high | The authenticated production home page still fetches the backend through `http://127.0.0.1:8723/api/health`, which is the user's local machine from the browser's perspective. This makes the signed-in production page show `Backend unreachable: Failed to fetch` even though the public backend health endpoint works. | After successful OAuth, the page body at `https://trade.guangai.ai/` contains `Backend unreachable: Failed to fetch`. Source: `workbench/frontend/src/app/(protected)/page.tsx` defaults `HEALTH_URL` to `http://127.0.0.1:8723/api/health` when `NEXT_PUBLIC_WORKBENCH_HEALTH_URL` is unset. | In production, make the browser fetch the public same-origin route, e.g. `/api/health`, or set `NEXT_PUBLIC_WORKBENCH_HEALTH_URL=https://trade.guangai.ai/api/health` at build time. Add a regression test so production builds do not ship localhost-only health URLs. |

## Not Completed

The real browser non-allowlist Google-account rejection path was not completed
because no non-allowlisted interactive Google account was available in the
controlled browser. The allowlist rejection logic remains covered by local
backend and frontend tests, but B021's L2 checklist asks for a real browser
attempt with a different Google account.

## Conclusion

Do not sign off B021 yet.

OAuth is now functional for the allowlisted account, but the signed-in
production home page still exposes a production/backend connectivity defect.
