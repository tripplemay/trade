# Workbench Architecture

Status: B020 dev-infrastructure snapshot.

This is the scaffolded architecture for the workbench-first path. B020
delivers only infrastructure and guardrails; business features begin in
later batches.

## Repository layout

```text
workbench/
├── backend/
│   ├── workbench_api/
│   │   ├── app.py
│   │   └── settings.py
│   └── tests/
│       ├── unit/
│       └── safety/
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   ├── lib/
│   │   ├── styles/
│   │   └── types/
│   └── tests/
│       ├── unit/
│       ├── safety/
│       └── e2e/
├── README.md
└── scripts/start_workbench.sh
```

## Backend

- FastAPI app factory in `workbench/backend/workbench_api/app.py`.
- Public surface lives under the `/api` prefix that nginx forwards in
  production (e.g. `GET /api/health`). B021 F001 also wires the first
  auth-gated probe, `GET /api/protected-test`.
- `workbench/backend/workbench_api/settings.py` uses an explicit env-var
  allowlist; B021 F001 adds `NEXTAUTH_SECRET` and `ALLOWED_USER_EMAIL`.
  The safety regression keeps the model and the allowlist in lockstep.
- Backend binds to `127.0.0.1` for local-only dev use.
- Tests are split into unit and safety guards.

## Frontend

- Next.js App Router scaffold in `workbench/frontend/src/app/page.tsx`.
- Placeholder home page renders scaffold status plus the canonical
  disclaimer.
- Canonical disclaimer text lives in `workbench/frontend/src/lib/disclaimer.ts`.
- `workbench/frontend/src/types/api.ts` is generated from backend
  OpenAPI via `scripts/generate-types.sh`.
- Vitest covers unit and safety checks.
- Playwright covers the minimal B020 browser smoke path.

## Safety boundaries

The B020 safety tests guard the current no-go surfaces:

- No broker SDK imports in backend or frontend.
- No paper/live broker URLs in backend source.
- No implicit environment-variable reads outside the allowlist.
- Canonical disclaimer visible on every navigable frontend route.

These are hard-boundary checks, not feature regression checks.

## CI

- `workbench-backend.yml` runs backend lint, type-check, unit tests, and
  safety guards.
- `workbench-frontend.yml` runs frontend lint, type-check, Vitest,
  OpenAPI drift detection, and Playwright smoke tests.
- `python-ci.yml` remains separate and continues to protect `trade/`.

## Batch boundary

- B021 adds cloud deploy and auth.
- B022 adds the first real workbench product surface.
- B023 adds the manual execution UI.

Do not move cloud, auth, or business logic into B020.

