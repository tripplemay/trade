# B022 Workbench Phase 1 Blocker 2026-05-18

## Scope

Codex ran B022 F014 first-round verification for the Phase 1 workbench.

Covered:
- L1 backend pytest / ruff / mypy
- L1 frontend lint / typecheck / vitest / build / Playwright
- Production `/api/health`, GitHub Actions deploy status, VM systemd limits, neighbor services
- Production anonymous OAuth gating for all 7 protected routes
- VM release layout for reports / runs directories
- Frontend production dependency audit

Not completed:
- Authenticated production browser walkthrough for the 7 pages, because the local Chrome session currently lands on `/login` and macOS blocks Codex from clicking the Google sign-in button through System Events.
- Production write-path checks for Recommendations export, Snapshot refresh, and Backlog CRUD. These were not executed because authenticated browser access was unavailable and production data writes require a tighter safety decision.

## Result

Do not sign off B022 yet.

L1 is green, but L2 has production blockers.

## Passing Evidence

### L1

- Backend: `../../.venv/bin/python -m pytest` -> `118 passed, 2 skipped`
- Backend: `../../.venv/bin/python -m ruff check .` -> pass
- Backend: `../../.venv/bin/python -m mypy` -> pass, 88 source files
- Frontend after `npm ci`: `npm run lint` -> pass
- Frontend: `npm run typecheck` -> pass
- Frontend: `npm test` -> `67 passed`
- Frontend: `npm run build` -> pass
- Playwright local on port 3099 with test auth env -> `14 passed`
- Local dev rewrite probe: `GET http://127.0.0.1:3099/api/health` returned backend JSON with `status=ok`, `db_connectivity=ok`, `version=72904f6`

Important caveat: the 14 Playwright checks only assert shell/card presence. The dev server logs show the B022 page data fetches return 404 in local dev because `next.config.mjs` only rewrites `/api/health` and `/api/protected-test`, not the new B022 `/api/*` routes.

### CI / Deploy / Health

- HEAD: `72904f644e1337dad0c11702c52c8d849a67118e`
- Production `/api/health.version`: `72904f644e1337dad0c11702c52c8d849a67118e`
- `Workbench Frontend CI` at `72904f6`: success
- `Workbench Deploy` at `72904f6`: success
- Production `/api/health` returned 200 with `status`, `version`, `db_connectivity`, `uptime_seconds`, `last_backup_age_seconds`, `last_backup_size_bytes`, `active_user_count`

### VM / Neighbors

`systemctl show workbench-backend.service workbench-frontend.service`:

```text
CPUQuotaPerSecUSec=2s
MemoryMax=2147483648
OOMScoreAdjust=500
ActiveState=active
SubState=running
```

Neighbors:
- `nginx` active
- PM2 `aigc-gateway`, `kolmatrix`, and `kolmatrix-staging` online
- `docker` active

### Anonymous OAuth Gating

All 7 protected routes redirect to `/login`:

```text
/ -> 307 https://trade.guangai.ai/login
/strategies -> 307 https://trade.guangai.ai/login?callbackUrl=%2Fstrategies
/backtest -> 307 https://trade.guangai.ai/login?callbackUrl=%2Fbacktest
/reports -> 307 https://trade.guangai.ai/login?callbackUrl=%2Freports
/recommendations -> 307 https://trade.guangai.ai/login?callbackUrl=%2Frecommendations
/snapshots -> 307 https://trade.guangai.ai/login?callbackUrl=%2Fsnapshots
/backlog -> 307 https://trade.guangai.ai/login?callbackUrl=%2Fbacklog
```

## Blocking Findings

| ID | Severity | Finding | Evidence | Required Fix |
|---|---|---|---|---|
| B022-F009-1 | high | Production release does not include the markdown reports directory, so the Reports page cannot render B019 retune sweep matrix or any historical reports. | On VM: `reports_dir /srv/workbench/releases/72904f644e1337dad0c11702c52c8d849a67118e/docs/test-reports False`; service-level check returned `reports_count 0`. | Deploy `docs/test-reports/` with the release, or set `WORKBENCH_REPORTS_DIR` to a real mounted directory containing the expected reports. Re-run production `/reports` browser verification for B019 matrix sorting and cross-links. |
| B022-F010-1 | high | Production has no configured writable runs directory for recommendation export tickets. The default resolves under the release path and currently does not exist. | On VM: `runs /srv/workbench/releases/72904f644e1337dad0c11702c52c8d849a67118e/docs/runs False`; `/var/lib/workbench/runs` also missing. | Configure `WORKBENCH_RUNS_DIR=/var/lib/workbench/runs` or another deploy-owned writable path and create it with correct ownership. Re-run Recommendations export L2 and verify the markdown contains the required research-only disclaimer. |
| B022-F014-DEV | high | Local dev does not proxy the new B022 API routes to FastAPI, and the E2E suite still passes despite API 404s. This violates the F014 intent of walking the 7 routes without console/API errors. | During Playwright run, Next dev logged `GET /api/dashboard 404`, `/api/strategies 404`, `/api/recommendations/current 404`, `/api/snapshots 404`, `/api/backlog 404`, `/api/reports 404`. `next.config.mjs` rewrites only `/api/health` and `/api/protected-test`. `protected-routes.spec.ts` explicitly says dashboard cards can pass even if `/api/dashboard` fails. | Add dev-only rewrite coverage for the B022 backend API routes while excluding `/api/auth/*`, and strengthen Playwright to fail on unexpected 4xx/5xx API responses and console errors. |
| B022-F014-1 | medium | Authenticated production browser L2 cannot be completed from the current Codex session. Chrome lands on `/login`; AppleScript JavaScript execution is disabled and System Events click failed with macOS error `-25200`. | Screenshot `/tmp/b022-home.png` shows `https://trade.guangai.ai/login` with the Google sign-in button. Attempted System Events click returned error `-25200`. | Provide an already-authenticated Chrome remote-debugging session, enable the required browser automation permissions, or have the user complete Google sign-in before Codex resumes L2. |
| B022-F001-SEC | high | Production frontend dependency audit reports direct high-severity vulnerabilities in `next@14.2.33`, plus a high advisory for Playwright in the test dependency tree. | `npm audit --omit=dev --json` reports `next` high severity advisories affecting `<14.2.34`, `<14.2.35`, and broader ranges including DoS / SSRF / middleware bypass classes; `playwright <1.55.1` high. | Upgrade Next.js to a patched release compatible with the app, and update Playwright. At minimum, document a security exception if deferring. |

## Required Action

Generator should fix the production deploy/runtime configuration before Codex reverifies:

1. Ensure `WORKBENCH_REPORTS_DIR` points to real production markdown reports and B019 is present.
2. Ensure `WORKBENCH_RUNS_DIR` points to a writable deploy-owned directory outside the read-only release, preferably `/var/lib/workbench/runs`.
3. Add local dev rewrite coverage for B022 `/api/*` routes and make E2E fail on unexpected API 404s / console errors.
4. Decide how authenticated L2 browser access will be provided for Codex.
5. Address or explicitly defer the high-severity npm audit findings.

## Conclusion

B022 remains in `fixing`.

The local implementation tests are strong, but production cannot yet satisfy the F009/F010/F014 L2 acceptance criteria.
