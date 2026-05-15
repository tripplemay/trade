# B021 Workbench Cloud Deploy & Auth Spec

## Background

B020 (`docs/test-reports/B020-dev-infrastructure-signoff-2026-05-15.md`) delivered the workbench's dev tooling layer — directory skeleton, CI workflows, testing strategy, safety guards, OpenAPI ↔ TypeScript pipeline, dev docs. `trade/` package stays pure stdlib; workbench/ has its own dependency graph isolated by design.

ADR `docs/adr/2026-05-15-workbench-direction.md` (cloud addendum) chose to deploy the workbench to the user's existing GCP VM (`kolmatrix-vps`, 34.180.93.185, shared with kolquest + apify-kol + pm2 aigcgateway) at `https://trade.guangai.ai`, single-user-gated via Google OAuth. User-side 5 prep items completed 2026-05-15 (`docs/dev/B021-vm-setup-runbook.md`).

B021 turns the workbench from a localhost dev fixture into the actual cloud-deployed surface that B022 (Phase 1 pages) and B023 (Phase 2 manual execution) will build features on top of. This batch **does not** ship any business pages — only authentication, persistence, deployment, and operational concerns.

## Goal

Ship the cloud-deployment + auth + persistence layer for the workbench:

1. Google OAuth gates every workbench route (except `/api/health` + `/api/auth/*`); only the single allowlisted email succeeds; non-allowlisted user gets 403.
2. SQLite + Alembic migrations under `/var/lib/workbench/db/` (or local path in dev); Repository-pattern data access layer; `accounts/me.json` / `backlog.json` continue to work as bootstrap sources but DB is the run-time source of truth.
3. Workbench deploys to `https://trade.guangai.ai`: nginx vhost (reusing existing nginx serving kolquest.com + staging.kolmatrix), Let's Encrypt cert via certbot, systemd units `workbench-backend.service` + `workbench-frontend.service` with explicit `CPUQuota=200%` + `MemoryMax=2G` fences.
4. CI/CD pipeline: push to `main` → tests → build → SSH deploy to `deploy@34.180.93.185` → health check → symlink-rollback on failure. Uses the 7 GitHub Secrets that the B021 prep set up.
5. Backup automation: SQLite snapshot via systemd timer → gzip → upload to `gs://trade-workbench-backups-gen-lang-client-0229748590/`; 30 daily + 12 monthly retention; restore script. Requires VM SA scope expansion (planned ~30-60s downtime — surfaced as F005 manual prereq).
6. Observability: enriched `/api/health` (version + DB connectivity + last backup timestamp) + structured request logs (request_id + user_id) + uvicorn access log on disk. Optional Sentry integration left as opt-in env var.
7. Codex L1 + L2 verification + signoff. L2 = end-to-end deploy walkthrough on the actual VM (not staging — this project has no staging path by design).

B021 introduces no business pages, no UI for execution, no satellite strategies. Those are B022 / B023 / BL-B011-S2 / etc.

## Hard Decisions

### Architecture (locked from ADR cloud addendum)

- **Hosting:** GCP VM `kolmatrix-vps` (34.180.93.185), Ubuntu 22.04, systemd 249. Co-hosted with kolquest + apify-kol + pm2 aigcgateway. Resource isolation enforced via systemd `CPUQuota=200%` + `MemoryMax=2G` on workbench-backend + workbench-frontend units.
- **Reverse proxy:** existing nginx (sites-enabled already has `kolquest.com` + `staging.kolmatrix`). New server block for `trade.guangai.ai` + `nginx -t` validation before reload.
- **TLS:** Let's Encrypt via certbot (`certbot --nginx`); auto-renewal via existing cron / systemd timer.
- **App backend:** FastAPI + Pydantic v2 + Uvicorn, run by `workbench-backend.service`. Bound to `127.0.0.1:8723`; only nginx talks to it.
- **App frontend:** Next.js 14 production build (`next build` standalone), served by nginx as static + `next start` for SSR routes via `workbench-frontend.service` bound to `127.0.0.1:3000`. Alternative: `next export` static-only — explicitly rejected because the OAuth callback is a Next.js Route Handler that needs `next start` runtime.
- **Database:** SQLite, file at `/var/lib/workbench/db/workbench.db` (already created in B021 prep #3 with deploy:deploy ownership and chmod 700). Alembic for schema migrations; migration files committed under `workbench/backend/workbench_api/db/migrations/`.
- **Auth:** Google OAuth via NextAuth.js v5 (Auth.js) on the frontend; backend reads NextAuth's JWT cookie and validates server-side. Single-email allowlist via env var `ALLOWED_USER_EMAIL`. Sessions: JWT cookies (no DB session store — workbench is single-user, simplest possible).
- **Backup:** systemd timer triggers a bash script that runs `sqlite3 workbench.db ".backup /tmp/staging.db"`, gzips, uploads to GCS, and prunes. Retention: keep 30 most recent daily + 12 most recent monthly; everything else deleted. Restore script reverses the pipeline.

### Resource isolation (non-negotiable)

The VM hosts production traffic for kolquest.com + aigcgateway. Workbench MUST NOT cause user-facing downtime for these services.

- `CPUQuota=200%` (max 2 CPU cores) + `MemoryMax=2G` per workbench-backend.service and workbench-frontend.service.
- systemd `OOMScoreAdjust=500` for workbench services (preferentially OOM-killed over neighbor services). Neighbors (aigcgateway pm2, kolquest, apify-kol containers) keep default OOMScoreAdjust=0.
- Network: workbench listens only on 127.0.0.1 (loopback); nginx is the public-facing point. No new public port opens.
- Disk: `/var/lib/workbench/` already isolated by B021 prep #3. Logs rotate via logrotate (configured in F003).

### Safety boundaries (non-negotiable, all inherited from B012 + B020 + extended for cloud)

- **No broker SDK / no paper or live API URLs:** the safety regression tests scaffolded in B020 F003 continue running in CI; B021 must not introduce any forbidden import or URL string.
- **No order placement:** B021 introduces auth + DB + deploy infra; the actual `/api/recommendations/export-ticket` Markdown output is B022's concern, and `/api/execution/*` is B023's. B021 ships zero endpoints that emit anything that could be construed as an order.
- **Single-user only:** OAuth allowlist contains exactly one email (`ALLOWED_USER_EMAIL`); user registration UI does not exist; "create account" buttons do not exist; sessions cannot be created for non-allowlisted users.
- **No secret in repo:** all secrets (OAuth client secret, NextAuth secret, SSH key, allowed email) live in GitHub Secrets and systemd `EnvironmentFile=/etc/workbench/workbench.env` (chmod 600 root:root, **never** committed). Regression test: `git ls-files | xargs grep -l 'GOCSPX-\|-----BEGIN' || true` returns empty.
- **No AI auto-decision:** B021 does not introduce any LLM / auto-decision path; manual user clicks remain the only mutation trigger.
- **Disclaimer on every page:** the B020 F003 disclaimer-present.spec.ts test continues to gate every new route; B022 will add many routes and each must inherit the Footer.

### CI/CD pipeline (F004)

- Trigger: push to `main`.
- Stages: lint + typecheck + unit tests + Playwright E2E (existing from B020) → build → SSH deploy → health check → declare success or rollback symlink.
- Pre-flight grep (CI fails if hit): any active secret value matches literal text `PLACEHOLDER-REPLACE-ME`. This is the framework-rule safety belt established when placeholders were pre-staged.
- Rollback model: each deploy lands at `/srv/workbench/releases/<timestamp>/`; symlink `/srv/workbench/current` points at the active release. If health check fails post-deploy, CI re-points symlink to the previous release and `systemctl restart workbench-backend workbench-frontend`.
- Deployment target user: `deploy@34.180.93.185`. SSH key from `DEPLOY_SSH_PRIVATE_KEY` GitHub Secret. Constrained sudoers (B021 prep #3) allows only `systemctl restart workbench-{backend,frontend}.service` + `daemon-reload` + `status`.

### User-action prerequisites (already completed in B021 prep, except scope expansion)

The 5 prep items have been completed 2026-05-15 (see `docs/dev/B021-vm-setup-runbook.md`). One additional manual action remains, but it's an F005 prereq, not a batch-wide blocker:

**F005 prereq — VM service account scope expansion**:
- Current VM SA has `https://www.googleapis.com/auth/devstorage.read_only` scope, which makes backup writes to GCS fail even though IAM grants `roles/storage.objectAdmin`.
- Fix: stop VM → `gcloud compute instances set-service-account kolmatrix-vps --service-account=$VM_SA --scopes=cloud-platform` → start VM. ~30-60s downtime for all co-hosted services (kolquest.com, staging.kolmatrix, apify-kol-service, pm2 aigcgateway).
- This is surfaced as a user-action item in F005 spec acceptance; Generator cannot run it (requires VM stop).

## Architecture

### Project structure delta from B020

```
workbench/
├── backend/
│   ├── pyproject.toml                              # B020 baseline + new deps:
│   │                                                #   sqlalchemy + alembic + python-jose[cryptography] + httpx (already)
│   ├── workbench_api/
│   │   ├── app.py                                  # B020 baseline + auth middleware mount
│   │   ├── settings.py                             # B020 baseline + expanded env allowlist
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── jwt_validator.py                    # Validates NextAuth JWT cookie
│   │   │   ├── dependency.py                       # FastAPI Depends for protected routes
│   │   │   └── tests/
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── engine.py                           # SQLAlchemy engine factory
│   │   │   ├── session.py                          # Session dependency for FastAPI
│   │   │   ├── models/                             # Declarative models
│   │   │   │   ├── account.py
│   │   │   │   ├── backlog_entry.py
│   │   │   │   └── snapshot_meta.py
│   │   │   ├── repositories/
│   │   │   │   ├── base.py
│   │   │   │   ├── account.py
│   │   │   │   ├── backlog.py
│   │   │   │   └── snapshot.py
│   │   │   └── migrations/
│   │   │       ├── env.py                          # Alembic env
│   │   │       └── versions/
│   │   │           └── 0001_initial.py             # Schema baseline
│   │   └── observability/
│   │       ├── logging.py                          # Structured log formatter (request_id + user_id)
│   │       └── health.py                           # Enhanced /api/health with DB + backup checks
│   └── tests/
├── frontend/
│   ├── package.json                                # B020 baseline + next-auth + @auth/core
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx                          # B020 baseline + SessionProvider wrap
│   │   │   ├── api/
│   │   │   │   └── auth/
│   │   │   │       └── [...nextauth]/
│   │   │   │           └── route.ts                # NextAuth route handler (Google provider)
│   │   │   ├── login/
│   │   │   │   └── page.tsx                        # Google login button only — no register UI
│   │   │   └── (protected)/                        # Route group; layout enforces session
│   │   │       ├── layout.tsx                      # SSR check session; redirect to /login if absent
│   │   │       └── page.tsx                        # Placeholder Home (B020 placeholder) moved here
│   │   ├── lib/
│   │   │   ├── auth.ts                             # NextAuth config (Google + JWT + allowlist)
│   │   │   └── api-client.ts                       # Frontend HTTP client with JWT propagation
│   │   └── middleware.ts                           # Auth middleware for protected routes
│   └── tests/
└── deploy/
    ├── nginx/
    │   └── trade.guangai.ai.conf                   # nginx server block (template; deploy substitutes)
    ├── systemd/
    │   ├── workbench-backend.service
    │   └── workbench-frontend.service
    ├── scripts/
    │   ├── deploy.sh                               # Runs on VM during CI deploy step
    │   ├── rollback.sh                             # Symlink flip + restart
    │   └── healthcheck.sh                          # Post-deploy health check
    └── backup/
        ├── workbench-backup.sh                     # SQLite snapshot + gzip + GCS upload + prune
        ├── workbench-backup.service                # systemd one-shot
        ├── workbench-backup.timer                  # daily at 03:00 VM local time
        └── workbench-restore.sh                    # Download from GCS + ungzip + restore
```

### Request lifecycle (with auth)

```
Browser ──→ https://trade.guangai.ai/some/route
                │
                ├─ nginx terminates TLS, forwards to 127.0.0.1:3000 (frontend) or 127.0.0.1:8723 (backend /api/*)
                │
                ├─ Next.js middleware checks for NextAuth JWT cookie
                │   ├─ absent → redirect to /login
                │   └─ present → verify signature with NEXTAUTH_SECRET
                │
                ├─ /login → renders "Sign in with Google" button only
                │       │
                │       ├─ NextAuth.js redirects to Google OAuth
                │       ├─ Google returns auth code → NextAuth exchanges for tokens
                │       ├─ Check tokens.email == ALLOWED_USER_EMAIL
                │       │     ├─ match → set JWT cookie, redirect to /
                │       │     └─ mismatch → render 403 "Not allowed"
                │
                └─ /api/* → backend FastAPI route
                    │
                    ├─ JWT cookie validator dependency
                    │   ├─ valid + email matches allowlist → request proceeds
                    │   ├─ valid + email mismatch → 403
                    │   └─ absent / invalid → 401
                    │
                    └─ Route handler uses DB session dependency
```

### Backup lifecycle (systemd timer daily at 03:00)

```
workbench-backup.timer (daily 03:00) → workbench-backup.service (one-shot) →
  /opt/workbench/scripts/workbench-backup.sh:
    1. sqlite3 /var/lib/workbench/db/workbench.db ".backup /tmp/wb-$(date +%Y%m%d).db"
    2. gzip /tmp/wb-*.db
    3. gcloud storage cp /tmp/wb-*.db.gz gs://trade-workbench-backups-.../daily/
    4. (1st of month) gcloud storage cp ... gs://.../monthly/
    5. Prune: keep last 30 daily + 12 monthly; delete rest via gcloud storage rm
    6. rm /tmp/wb-*
    7. Append result to /var/log/workbench/backup.log
```

## Feature Requirements

### F001 — Google OAuth integration (NextAuth + backend session validation)

Executor: generator.

Frontend: install `next-auth@5` + `@auth/core`; configure Google provider with `GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET` from env; `NEXTAUTH_SECRET` for JWT signing; redirect URI `https://trade.guangai.ai/api/auth/callback/google`. `/api/auth/[...nextauth]/route.ts` mounts the NextAuth route handlers. `/lib/auth.ts` exports a `signIn` callback that checks `profile.email === process.env.ALLOWED_USER_EMAIL` and returns `false` for non-allowlisted users (causing NextAuth to render error page). `middleware.ts` enforces JWT cookie on every route under `/(protected)/` and `/api/(backend-proxy)/`.

Backend: install `python-jose[cryptography]`; new module `workbench_api/auth/jwt_validator.py` reads the JWT cookie set by NextAuth, verifies signature with `NEXTAUTH_SECRET`, extracts email, checks against `ALLOWED_USER_EMAIL`. `workbench_api/auth/dependency.py` exports `require_authenticated_user()` as a FastAPI dependency. New env vars added to settings allowlist: `NEXTAUTH_SECRET`, `ALLOWED_USER_EMAIL`. Backend `/api/health` remains public (no auth) — needed for nginx upstream health check and external uptime monitors.

Local dev: NextAuth in dev mode auto-allows `localhost:3000` redirect; safety regression test (new) asserts production build refuses HTTP / non-trade.guangai.ai redirect URIs.

Acceptance:

1. Unauthenticated visit to `/` → redirect to `/login`.
2. Click "Sign in with Google" → Google OAuth flow → success returns to `/`.
3. Sign in with non-allowlisted account → NextAuth signIn callback returns false → error page with text "This workbench is restricted to a single authorized user."
4. Authenticated `/api/protected-test` (new placeholder route) returns 200 with the user email; unauthenticated returns 401; non-allowlisted JWT (manually crafted) returns 403.
5. `GET /api/health` continues to return 200 without auth (needed for healthcheck).
6. All B020 tests still green; new auth tests pass (pytest + Vitest).
7. Safety regression: NextAuth callback URL must contain `trade.guangai.ai` in production env; new test asserts so.

### F002 — SQLite + Alembic migrations + Repository data layer

Executor: generator.

Backend `workbench_api/db/`:

- `engine.py`: SQLAlchemy 2.x engine factory; reads `WORKBENCH_DB_URL` from env (e.g. `sqlite:////var/lib/workbench/db/workbench.db` in prod; `sqlite:///./workbench-dev.db` in dev).
- `session.py`: FastAPI dependency yielding a Session per-request; commits on success, rolls back on exception.
- `models/`: declarative ORM models for:
  - `Account` (account_id PK, name, base_currency, cash, equity_value, as_of_date) — mirrors B012 `accounts/me.json` schema.
  - `BacklogEntry` (id PK, title, description, priority, decisions JSON, confirmed_at, source) — mirrors `backlog.json`.
  - `SnapshotMeta` (snapshot_id PK, manifest_path, quality_status, created_at) — registry of snapshots; actual data still lives in `data/public-cache/*.json`.
- `repositories/`: thin wrappers exposing `get_by_id`, `list_all`, `upsert`, `delete` per model. Pure ORM, no business logic.

Alembic:

- `migrations/env.py` configured to use `engine.py`.
- `migrations/versions/0001_initial.py` creates the 3 tables.
- `scripts/migrate.sh` runs `alembic upgrade head` from `workbench/backend/`.

Bootstrap: a one-shot CLI `workbench-bootstrap` (entry point in `pyproject.toml`) reads `accounts/me.json` + `backlog.json` if present in repo root and `upsert`s rows into DB. Idempotent.

Acceptance:

1. `alembic upgrade head` on a fresh DB creates the 3 tables; running again is no-op.
2. `workbench-bootstrap` from a fresh state imports `accounts/me.json` + `backlog.json` 4 entries; running again is idempotent.
3. Repository methods round-trip via pytest (create / read / update / delete each model).
4. Backend `/api/health` extended to include `"db_connectivity": "ok"` (raises 500 otherwise).
5. Local dev: env var `WORKBENCH_DB_URL=sqlite:///./workbench-dev.db` works without `/var/lib/workbench/db/` existing.
6. Safety regression: new test asserts no `psycopg2` / `mysqlclient` / `pymongo` import (we are SQLite-only in B021).

### F003 — Dockerfile-free deploy artifacts: systemd units + nginx vhost + certbot

Executor: generator.

Deliverables in `workbench/deploy/`:

- `systemd/workbench-backend.service`: runs `uvicorn workbench_api.app:app --host 127.0.0.1 --port 8723` as `deploy:deploy`; `EnvironmentFile=/etc/workbench/workbench.env`; `CPUQuota=200%`; `MemoryMax=2G`; `OOMScoreAdjust=500`; `Restart=on-failure`; `RestartSec=5s`.
- `systemd/workbench-frontend.service`: runs `node /srv/workbench/current/frontend/.next/standalone/server.js` (Next.js standalone output) on 127.0.0.1:3000 with the same isolation knobs.
- `nginx/trade.guangai.ai.conf`: server block; `ssl_certificate` + `ssl_certificate_key` paths point at certbot output; `proxy_pass http://127.0.0.1:3000` for `/*`; `proxy_pass http://127.0.0.1:8723` for `/api/*`; standard `proxy_set_header` for `Host` / `X-Forwarded-*` so NextAuth sees the right hostname; `gzip on`; `client_max_body_size 10m` (fill upload future-proofing).
- `scripts/deploy.sh`: copies artifacts, runs `systemctl daemon-reload`, runs `systemctl restart workbench-backend.service workbench-frontend.service`, exits non-zero on failure.
- `scripts/healthcheck.sh`: curls `https://trade.guangai.ai/api/health` 10 times with 2s interval; passes if any returns 200 with `"db_connectivity":"ok"`.

Certbot: F003 includes a one-time-run document `workbench/deploy/CERTBOT-SETUP.md` for the user to run `certbot --nginx -d trade.guangai.ai` manually after the first nginx vhost is in place. Auto-renewal handled by certbot's existing systemd timer (already enabled for kolquest.com).

Resource quota validation: F003 adds a verification step (`systemctl show workbench-backend.service | grep -E 'CPUQuota|MemoryMax|OOMScoreAdjust'`) that Codex F006 must run on the actual VM to confirm the limits are applied.

Acceptance (parts verified by Codex F006):

1. `nginx -t` succeeds with the new server block added.
2. `systemctl status workbench-backend.service workbench-frontend.service` shows active (running) after deploy.
3. `curl https://trade.guangai.ai/api/health` returns 200 from external network.
4. `systemctl show workbench-backend.service` confirms `CPUQuota=200%` + `MemoryMax=2147483648` (2 GiB in bytes).
5. Loading `https://trade.guangai.ai/` redirects to `/login` (auth wired through nginx).
6. Bandwidth check: `htop` / `top` on VM during a deploy shows workbench services bound by quota, kolquest / aigcgateway unaffected.

### F004 — CI/CD pipeline (GitHub Actions push → SSH deploy → health check → rollback)

Executor: generator.

New workflow `.github/workflows/workbench-deploy.yml`:

- Triggered: push to `main` after `workbench-backend` + `workbench-frontend` CI workflows pass (uses `workflow_run` chained trigger).
- Env: `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: "true"` (per framework v0.9.23 #2).
- Pre-flight: a step that greps the workflow file + repo for the literal text `PLACEHOLDER-REPLACE-ME` and fails the workflow if found. Belt-and-braces against placeholders going to production.
- Steps:
  1. Checkout
  2. Build backend: `python -m build` (sdist + wheel)
  3. Build frontend: `npm ci && npm run build` → `.next/standalone/` + `.next/static/`
  4. SCP artifacts to `deploy@$DEPLOY_HOST:/srv/workbench/releases/$GITHUB_SHA/`
  5. SSH run `bash deploy/scripts/deploy.sh /srv/workbench/releases/$GITHUB_SHA/` which symlinks `/srv/workbench/current → $GITHUB_SHA`, restarts services
  6. SSH run `bash deploy/scripts/healthcheck.sh` — if fails, run `bash deploy/scripts/rollback.sh` (symlink to previous release + restart) and fail the workflow
  7. Post-success: SSH run `find /srv/workbench/releases -mindepth 1 -maxdepth 1 -mtime +30 -exec rm -rf {} +` to GC old releases > 30 days

Pre-flight grep guard (CI fails if hit) over secrets: GitHub Secrets cannot be programmatically read in workflow context, but we CAN check that, if the workflow uses them, the resulting auth attempt would fail loud — we don't need to grep value, we need to make sure the workflow's healthcheck endpoint sees a working login flow. So F004's pre-flight grep is over the **artifact files** for the `PLACEHOLDER-REPLACE-ME` string before SCP. If a placeholder ever leaks into source it stops here.

Acceptance:

1. Push to `main` after F001-F003 lands triggers `workbench-deploy.yml`; workflow goes green.
2. Workflow log shows: build, scp, deploy, healthcheck — each step exits 0; total < 10 minutes.
3. After deploy, `https://trade.guangai.ai/api/health` returns the new `GITHUB_SHA` in `version` field.
4. Intentional break of the healthcheck (throwaway commit that makes `/api/health` return 500) → workflow runs deploy, healthcheck fails, rollback.sh runs, symlink flips back, services restart, workflow exits non-zero, `https://trade.guangai.ai/api/health` still returns the previous SHA.
5. Pre-flight `PLACEHOLDER-REPLACE-ME` grep fails on intentional throwaway commit that re-adds placeholder string.

### F005 — Backup automation (SQLite snapshot → GCS, retention, restore)

Executor: generator (with one user-action manual prereq before deploy).

Deliverables in `workbench/deploy/backup/`:

- `workbench-backup.sh`: bash script (run as deploy user) executing:
  1. `sqlite3 /var/lib/workbench/db/workbench.db ".backup /tmp/wb-$(date +%Y%m%d-%H%M%S).db"` (consistent snapshot, no DB lock contention)
  2. `gzip /tmp/wb-*.db` (output `.db.gz`)
  3. `gcloud storage cp /tmp/wb-*.db.gz gs://trade-workbench-backups-gen-lang-client-0229748590/daily/`
  4. On 1st of month: also copy to `gs://.../monthly/`
  5. Prune: keep 30 newest in `daily/`, 12 newest in `monthly/`, delete the rest with `gcloud storage rm`
  6. `rm /tmp/wb-*` cleanup
  7. Append summary line to `/var/log/workbench/backup.log` (timestamp + filename + size + duration + outcome)
- `workbench-backup.service` (systemd one-shot, User=deploy): runs the script
- `workbench-backup.timer` (daily 03:00 VM local time, Persistent=true so missed runs catch up at boot)
- `workbench-restore.sh`: takes a backup filename arg; downloads + ungzips + replaces `workbench.db` (asks for confirmation in interactive mode; `--force` flag for scripted use)

**Manual user prereq for F005:** VM service account scope expansion. Generator cannot perform this (requires VM stop). F005 acceptance includes a sub-step where the user runs:

```bash
gcloud compute instances stop kolmatrix-vps --zone=asia-northeast1-b
gcloud compute instances set-service-account kolmatrix-vps \
  --zone=asia-northeast1-b \
  --service-account=1044753973286-compute@developer.gserviceaccount.com \
  --scopes=cloud-platform
gcloud compute instances start kolmatrix-vps --zone=asia-northeast1-b
```

Expected impact: ~30-60s downtime for kolquest.com, staging.kolmatrix, apify-kol-service, pm2 aigcgateway. The user should schedule this during low-traffic window for those services.

Verification after scope expansion (Generator runs):

- `curl -s -H "Metadata-Flavor: Google" http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/scopes` shows `cloud-platform` or `devstorage.read_write`.
- `sudo -u deploy gcloud storage cp /etc/hostname gs://trade-workbench-backups-gen-lang-client-0229748590/test.txt && gcloud storage rm gs://.../test.txt` succeeds.

Acceptance:

1. Manual prereq done; metadata server confirms `cloud-platform` scope.
2. `systemctl start workbench-backup.service` runs successfully; backup file appears in `gs://.../daily/`; log line written.
3. `systemctl status workbench-backup.timer` shows enabled + active; next trigger date present.
4. Retention test: pre-seed 35 daily files in GCS by repeating step 2 with mtime hack; trigger the timer; verify 30 newest remain, 5 oldest deleted.
5. Restore test: take a fresh backup; corrupt the live DB; run `workbench-restore.sh <backup-filename> --force`; verify DB is restored to pre-corruption state.
6. Backup log file at `/var/log/workbench/backup.log` exists, owned by deploy:deploy, chmod 644; logrotate rule rotates monthly.

### F006 — Observability + healthcheck + Codex L1+L2 verification + signoff

Executor: codex.

Enhanced `/api/health` (F002 baseline + F006 enrichment):

```json
{
  "status": "ok",
  "version": "<git_sha>",
  "uptime_seconds": 12345,
  "db_connectivity": "ok",
  "last_backup_age_seconds": 86400,
  "last_backup_size_bytes": 12345,
  "active_user_count": 1
}
```

Structured logging:

- Backend logs via `workbench_api/observability/logging.py` using Python `logging` + a JSON formatter. Every line includes `timestamp` + `level` + `request_id` (from ASGI middleware) + `user_id` (from auth dependency if authenticated) + `event` + free-form fields.
- Logs written to `/var/log/workbench/app.log` (rotated via logrotate, weekly).
- Uvicorn access log redirected to `/var/log/workbench/access.log`.

Optional Sentry: read `SENTRY_DSN` env var (added to settings allowlist); if set, initialize `sentry-sdk[fastapi]`. If unset, no-op. (Sentry not required for B021 acceptance — opt-in for user.)

Codex verification (L1 + L2 + signoff):

L1 checklist (in-CI):

1. `npm test --prefix workbench/frontend` green (Vitest); covers auth wiring unit tests, NextAuth config, middleware.
2. `pytest workbench/backend/tests -q` green; covers `auth/`, `db/repositories/`, `observability/health`.
3. `ruff check workbench/backend` clean.
4. `mypy workbench/backend` clean.
5. Safety regression tests still green (no broker SDK / no paper or live URL / no secret in repo / disclaimer present on all routes including new auth pages).
6. Playwright E2E smoke walks `/login` → mock Google OAuth → land on `/` → see disclaimer; covers happy path.

L2 checklist (on the actual VM after first deploy):

7. From browser on user's laptop: visit `https://trade.guangai.ai/`; redirected to `/login`; sign in with `tripplezhou@gmail.com`; land on `/`; see placeholder card + disclaimer.
8. From browser, sign in with a different Google account (e.g., a personal Gmail not in allowlist): page renders "restricted" error; no session created; `/api/health` accessible (no auth required) but `/api/protected-test` returns 403.
9. From local terminal: `curl https://trade.guangai.ai/api/health` returns 200 with `version=<git_sha>` matching `git rev-parse HEAD` on `main`.
10. SSH to VM, run `systemctl show workbench-backend.service workbench-frontend.service | grep -E 'CPUQuota|MemoryMax|OOMScoreAdjust'`; confirm 200% / 2 GiB / 500 respectively.
11. `gs://trade-workbench-backups-gen-lang-client-0229748590/daily/` has at least one backup file after a manual `systemctl start workbench-backup.service`.
12. Resource neighbor check: `systemctl status nginx kolquest-app aigcgateway` (or equivalents) all "active (running)" with no recent restarts attributable to workbench.

Codex writes `docs/test-reports/B021-cloud-deploy-auth-signoff-2026-MM-DD.md` using `framework/templates/signoff-report.md`. Updates `progress.json` (`status → done`, `docs.signoff` set, `evaluator_feedback` summary).

## Out of Scope

- Any business UI pages (Home / Strategies / Backtest viewer / Reports / Recommendations / Snapshots / Backlog). Deferred to **B022**.
- Manual execution UI (target positions diff / order ticket / fill journal). Deferred to **B023**.
- Multi-user / registration / user invite. Permanent (PRD §5 — non-MVP).
- Auto broker connect / paper API / live API. Permanent (PRD §5).
- Cloud SQL / managed Postgres / multi-region. SQLite + single-VM is the design.
- Real-time data streams / WebSocket. Deferred to Phase 3+.
- Sentry / external APM integration as required. F006 ships only opt-in env-var-gated Sentry.
- Multi-region or geo-replicated backup. Single GCS bucket in same region as VM is the design; cross-region recovery is a separate batch if ever needed.
- Multi-environment (staging / production split). Single environment = `trade.guangai.ai`. The workbench dev experience uses local SQLite + `npm run dev`.

## Acceptance

Batch is **done** when:

1. F001 — F005 all green on `main`; existing CI workflows (python-ci + workbench-backend + workbench-frontend) all green; new `workbench-deploy.yml` workflow green.
2. F006 Codex L1 + L2 verification: all 12 checklist items pass; signoff written.
3. `https://trade.guangai.ai/` is live, gated by Google OAuth, allowlist enforced, disclaimer on every page.
4. `progress.json.status = done`; `docs.signoff` populated.
5. `/var/lib/workbench/db/workbench.db` exists; Alembic at head revision.
6. `gs://trade-workbench-backups-gen-lang-client-0229748590/` has at least one daily backup after F005 lands.
7. systemd `CPUQuota=200%` + `MemoryMax=2G` + `OOMScoreAdjust=500` applied to both workbench services.
8. No new secrets in git history; no broker SDK / paper or live URL strings; B020 safety regression tests + the new B021 safety regression tests all green.
9. Existing `trade/` test suite unaffected; co-hosted services (kolquest / aigcgateway / apify-kol) unaffected by the deploy.

_Disclaimer: research-only; never authorizes paper or live trading._
