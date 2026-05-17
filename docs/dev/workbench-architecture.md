# Workbench Architecture

Status: **B022 Phase 1 — shipped** (`https://trade.guangai.ai`).

This document describes the workbench surface as of B022 F012. B020 stood
up the empty scaffold, B021 added cloud + auth + SQLite, and B022 filled in
the seven research pages. B023 plans to layer manual-execution UI on top
of the same shell.

## Repository layout

```text
workbench/
├── backend/                       # FastAPI (Python 3.11+)
│   ├── workbench_api/
│   │   ├── app.py                 # FastAPI factory + /api/health + auth probe
│   │   ├── auth/                  # NextAuth JWT cookie verification
│   │   ├── db/                    # SQLAlchemy 2 + Alembic + Repository
│   │   ├── observability/         # structured logging, active-users counter
│   │   ├── routes/                # 1 router per F00x slice
│   │   ├── schemas/               # Pydantic v2 response/request shapes (F002)
│   │   ├── services/              # business logic: dashboard / strategies / docs
│   │   │                          #   reports / recommendations / snapshots
│   │   │                          #   backtests / backlog
│   │   ├── settings.py            # env-var allowlist + typed Settings
│   │   └── cli/bootstrap.py       # one-shot DB + secret bootstrap
│   └── tests/                     # pytest: unit/ + safety/
├── frontend/                      # Next.js 14 (TS strict, React 18, Tailwind 3)
│   ├── src/
│   │   ├── app/                   # App Router: (protected)/ + login + api/auth
│   │   ├── components/
│   │   │   ├── shell/             # TopBar / SideNav / ThemeProvider / nav-items
│   │   │   ├── ui/                # shadcn primitives (Button/Card/Dialog/…)
│   │   │   ├── chart/             # F004 lightweight-charts + ECharts wrappers
│   │   │   ├── table/             # F005 DataTable + column helpers
│   │   │   └── markdown/          # F009 markdown renderer + heavy-table swap
│   │   ├── lib/                   # auth helpers + fonts + sse-stream + utils
│   │   ├── styles/                # Tailwind + Zinc dark tokens + .numeric
│   │   └── types/api.ts           # OpenAPI-generated TS types
│   └── tests/
│       ├── unit/                  # Vitest (node + happy-dom mix)
│       ├── safety/                # no-broker-sdk, no-localhost, no-resizable…
│       └── e2e/                   # Playwright (setup + anon + authed projects)
├── deploy/
│   ├── nginx/trade.guangai.ai.conf
│   └── systemd/workbench-{backend,frontend}.service
└── scripts/start_workbench.sh
```

## Backend surface — endpoints, services, data

| Endpoint | Methods | Service module | Notes |
|---|---|---|---|
| `/api/health` | GET | (inline) | Public; nginx upstream probe + uptime monitors. 6 observability fields incl `version=<git_sha>`, `db_connectivity`, `last_backup_age_seconds`. |
| `/api/protected-test` | GET | (inline) | Auth probe; returns `{status, email}`. |
| `/api/dashboard` | GET | services/dashboard + services/reports_scanner | F006 — composes NAV from Account row(s), placeholder DD/kill-switch, recent_reports scanned off disk, action_items=[]. |
| `/api/strategies`, `/api/strategies/{id}` | GET, GET | services/strategies | F007 — hand-curated 4-sleeve registry (B013-regime-quarterly w/ B019 retune `activation_threshold=0.11`, B014/B015/B016 stubs). 404 on unknown id. |
| `/api/docs/{path:path}` | GET | services/docs | F007 — repo-relative file reader with traversal sanitiser (rejects `..`, abs paths, root-escape). Content-type by suffix. 400 / 404 on rejection / miss. |
| `/api/backtests/run`, `/api/backtests/{run_id}` | POST, GET | services/backtests | F008 — synthetic backtest engine (deterministic hash → 120-sample equity walk + 3 alloc + 12 trades), <100ms. In-memory cache + Lock. B023 wires real `trade.master.run_backtest`. |
| `/api/reports`, `/api/reports/{slug}` | GET, GET | services/reports | F009 — list reuses dashboard scanner; detail returns body markdown + extracted GFM tables + cross-link list. |
| `/api/recommendations/current`, `/api/recommendations/export-ticket` | GET, POST | services/recommendations | F010 — equal-weight target across 4 sleeves; placeholder gates; **export writes markdown checklist containing the literal research-only disclaimer**. |
| `/api/snapshots`, `/api/snapshots/refresh` | GET, POST (SSE) | services/snapshots | F011 — list from SnapshotMeta repo; refresh streams 5-stage synthetic SSE + upserts a SnapshotMeta row before the `complete` event. |
| `/api/backlog` + `/api/backlog/{id}` | GET, POST, PATCH, DELETE | services/backlog | F012 — BacklogRepository persistence + every mutation regenerates `backlog.json` + runs `git add` + `git commit -m 'chore(backlog): add\|edit\|delete BL-WB-XXXX'` via the injectable `GitRunner` Protocol. Commit failure → 500 fail-closed. |

### SQLite schema (B021 → B022)

| Table | Owner | Purpose |
|---|---|---|
| `account` | B021 F002 | Single research-account state (cash + equity_value + as_of_date). Read by F006 dashboard + F010 recommendations. |
| `snapshot_meta` | B021 F002 | Registry of public-data snapshots. Read by F011 list; written by F011 refresh complete-stage. |
| `backlog_entry` | B021 F002 | Mirror of `backlog.json`. CRUD'd by F012. |

Alembic owns the migration history under `workbench_api/db/migrations/`.
Production DB lives at `/var/lib/workbench/db/workbench.db`; daily backups
land in `gs://…/daily/` via the systemd backup unit (B021 F006).

### Env-var allowlist

`workbench_api.settings.ALLOWED_ENV_VARS` is the enforcement surface; any
new env var requires both an entry there and a matching `Settings` field.
The safety regression (`tests/safety/test_settings_env_allowlist.py`)
keeps both ends in lockstep. Current entries:

```
NEXTAUTH_SECRET, ALLOWED_USER_EMAIL, WORKBENCH_DB_URL, SENTRY_DSN,
WORKBENCH_BACKUP_LOG, WORKBENCH_LOG_DIR, WORKBENCH_REPORTS_DIR (F006),
WORKBENCH_RUNS_DIR (F010)
```

## Frontend shell + page composition

```text
Browser
└─ Next.js App Router
   ├─ /login (anonymous)
   └─ /(protected)/                     ← server layout: await auth() gate
      ├─ SessionProvider                ← client wrapper; useSession everywhere
      └─ ThemeProvider (dark-first)     ← next-themes wrapper
         └─ <div class="flex h-screen flex-col">
            ├─ TopBar       ← project name + research-only chip + sign-out
            ├─ <flex flex-1>
            │   ├─ SideNav  ← 7 nav items (single source: nav-items.ts)
            │   └─ <main>   ← per-page body
            └─ Footer       ← canonical disclaimer (Playwright pinned)
```

Each (protected)/ page is a client component that fetches data via
same-origin `/api/*` paths (framework v0.9.24 #3 — keep loopback URLs
out of the client bundle so nothing breaks at the browser host name).
`next.config.mjs` rewrites `/api/*` to `http://127.0.0.1:8723` in dev only;
in production nginx routes the same path to the FastAPI upstream before it
reaches the Next.js standalone server.

## Request lifecycle (read path)

```text
1. Browser fetch("/api/dashboard")
2. nginx (trade.guangai.ai) → upstream http://127.0.0.1:8723/api/dashboard
3. FastAPI middleware:
   - RequestIDMiddleware tags + structured-log
   - require_authenticated_user dependency:
     - extract authjs.session-token cookie
     - decode HS256 JWS via NEXTAUTH_SECRET
     - assert email == ALLOWED_USER_EMAIL
     - bump active_users counter (read back on /api/health)
4. Route handler (routes/dashboard.py) calls services/dashboard.build_dashboard
5. Service reads via Repository (SQLite) + scanner (filesystem)
6. Pydantic response_model validates + serializes
7. SessionDep commits the SQLAlchemy session; response → nginx → browser
```

## Request lifecycle (write path — F012 Backlog mutation)

```text
1. POST /api/backlog {title,description,priority}
2. auth + RequestID middleware (same as read)
3. services/backlog.create_backlog:
   a. BacklogRepository.upsert() + session.commit()
   b. _dump_rows_to_json(rows, backlog.json)
   c. GitRunner(['git','add','backlog.json'], cwd=repo_root)
   d. GitRunner(['git','commit','-m','chore(backlog): add BL-WB-XXXX'], cwd=repo_root)
4. GitCommitError → 500 fail-closed (frontend surfaces toast)
5. Else returns the new BacklogEntry
6. Frontend refetches list + toast.success
```

## SSE refresh (F011)

```text
POST /api/snapshots/refresh
└─ StreamingResponse(media_type='text/event-stream')
   └─ async generator yielding 5 stages (50ms apart):
      data: {"stage":"prepare", …}\n\n
      data: {"stage":"fetch",   …}\n\n
      data: {"stage":"process", …}\n\n
      data: {"stage":"store",   …}\n\n
      ── (upsert SnapshotMeta row to DB here)
      data: {"stage":"complete",…}\n\n
```

Frontend `src/lib/sse-stream.ts` consumes via `fetch + ReadableStream +
TextDecoder`, splits on blank lines, JSON-decodes each `data: ` line.
EventSource is not used because it cannot POST.

## Cloud deploy chain (B021 F003-F006 → carried into B022)

```text
git push origin main
└─ GitHub Actions (workbench-frontend.yml + workbench-backend.yml)
   ├─ ruff / mypy / pytest / vitest / playwright (anon + authed)
   └─ on success → workbench-deploy.yml (workflow_run trigger)
      ├─ Build backend wheel
      ├─ Build frontend (next build → .next/standalone)
      ├─ Pre-flight: refuse PLACEHOLDER-REPLACE-ME in workbench/ source
      ├─ Stage release tarball + RELEASE_SHA marker
      ├─ scp → VM /tmp/<release>.tgz
      ├─ ssh: unpack → /srv/workbench/<sha>/ → alembic upgrade → flip
      │        /srv/workbench/current symlink → restart systemd units
      │        (workbench-backend.service + workbench-frontend.service)
      ├─ post-deploy GET /api/health (expects status=ok + version=<sha>)
      └─ on failure: SSH — rollback step flips symlink back
```

The deploy user has a sudoers whitelist for `systemctl restart
workbench-backend.service` and `systemctl restart
workbench-frontend.service` (per-service, not combined). nginx + Let's
Encrypt + the SQLite→GCS backup unit are infrastructure (provisioned in
B021 prep) — deploys do not touch them.

## Safety boundary inventory

| Guard | Location | What it pins |
|---|---|---|
| Env-var allowlist | `tests/safety/test_settings_env_allowlist.py` | `ALLOWED_ENV_VARS` ↔ `Settings` lockstep |
| No broker SDK | backend `tests/safety/test_no_broker_sdk_imports.py` + frontend `tests/safety/no-broker-sdk-imports.spec.ts` | Reject `@alpaca/`, `ib-insync`, etc. |
| No paper/live URL | backend `tests/safety/test_no_paper_or_live_urls.py` | URL fragments forbidden in source |
| No SQLite driver alt | backend `tests/safety/test_no_non_sqlite_db_drivers.py` | Reject psycopg / pymysql etc. |
| No hardcoded backend host | frontend `tests/safety/no-hardcoded-backend-host.spec.ts` | `127.0.0.1:872X` / `localhost:872X` in `src/` |
| Production callback URL | frontend `tests/safety/production-callback-url.spec.ts` | `NEXTAUTH_URL` must contain `trade.guangai.ai` in production builds |
| Disclaimer on /login | frontend `tests/safety/disclaimer-present.spec.ts` (Playwright anon project) | Canonical disclaimer renders on the only anonymous route |
| Disclaimer on protected routes | frontend `tests/e2e/protected-routes.spec.ts` (Playwright authed project) | Disclaimer + TopBar + SideNav on every of the 7 routes |
| ResizablePanel only on Backtest | frontend `tests/safety/no-resizable-panel-outside-backtest.spec.ts` | F008 hard boundary — no other (protected)/ page may import the primitive |
| Export-ticket disclaimer literal | backend `tests/unit/test_recommendations.py` | F010 — exported markdown body must contain the `research-only; this is a manual review checklist, not a trading instruction` literal |
| Backlog git commit message | backend `tests/unit/test_backlog.py` | F012 — `chore(backlog): add\|edit\|delete <id>` format, fail-closed on git error |
| Pre-flight placeholder grep | `.github/workflows/workbench-deploy.yml` | `PLACEHOLDER-REPLACE-ME` rejected from `workbench/` source before deploy |

## CI pipelines

- **`workbench-backend.yml`** — ruff + mypy (strict, scans `workbench_api`
  and `tests`) + pytest (118 passing + 2 skipped after F012; STUB_ROUTES
  empties as each F006-F012 lands).
- **`workbench-frontend.yml`** — `npm ci` + OpenAPI drift check (regenerate
  `src/types/api.ts` from a live backend, `git diff --exit-code`) +
  ESLint (zero warnings) + tsc + vitest (67 tests) + Playwright (14 tests
  across setup/anon/authed projects, dev server booted via
  `start-server-and-test`).
- **`workbench-deploy.yml`** — `workflow_run` trigger after either CI
  green; build → SSH deploy → healthcheck → rollback-on-fail.
- **`python-ci.yml`** — still protects `trade/` (untouched by the workbench
  monorepo).

Add new workflows to `docs/dev/branch-protection-guidance.md` so the
required-status-check list stays current.

## Batch boundary reminder

- B020: scaffolding + safety guards + first CI pipelines.
- B021: cloud deploy + Google OAuth + SQLite + Alembic + Repository +
  systemd + nginx + cert + backup automation + observability fields on
  `/api/health`.
- **B022 (current): 7 research pages + 5 chart wrappers + AG Grid
  DataTable + markdown viewer + Recommendations export ticket + SSE
  refresh + Backlog CRUD with git auto-commit.**
- B023: manual execution UI (position diff / order ticket / fill journal)
  layered onto the same shell.

Do not move cloud, auth, broker, or execution logic into earlier batches.
