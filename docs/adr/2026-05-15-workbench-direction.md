# ADR 2026-05-15 — Workbench-First Direction (replaces B020 Manual-Execution-Helper plan)

## Status

Proposed (pending PRD §7 / §12 amendment, scheduled for the B019 done wrap-up)

## Context

After B019 planning, the project surfaced two competing routes for finishing the MVP:

1. **CLI Manual Execution Helper** (originally captured as the post-B019 next-batch decision on 2026-05-15 morning) — keep all interaction in the terminal: position diff CLI, order ticket Markdown, fill journal CSV. Single-batch, ~5 features, low dependency footprint.
2. **Workbench** — a graphical local web app where the user browses strategies, runs backtests, reads research reports, sees recommended portfolios, and (later) drives manual execution. Multi-batch, larger surface, higher polish.

The user (single individual investor, USD 100k–500k personal account, monthly/quarterly cadence) explicitly chose route 2 with the bar set at "professional financial tool quality (Bloomberg / TradingView / Koyfin level) with strong extensibility."

That bar is incompatible with the existing PRD §7 ("MVP 不实现正式前端 dashboard") which deferred any GUI to post-MVP. PRD §7 cited four reasons:

1. Backtest result schema not stable
2. Strategy config schema not stable
3. Data quality output not implemented
4. Premature UI risks fake-data dashboards and rework

Audit on 2026-05-15: reasons 1–3 are no longer true (B007 / B009 / B010 / B011 / B012 stabilized them); reason 4 is partially mitigated by the Phase-1/Phase-2 split that defers the still-fluid execution-layer schema to Phase 2.

## Decision

**Adopt the Workbench-First direction (Path A).** B020 becomes "Workbench Phase 1" instead of the Manual Execution Helper. Manual execution moves to a Workbench Phase 2 batch (B021). The original CLI helper batch is permanently retired — its workflow is absorbed into the workbench's UI flows.

### Sub-decisions (locked via planning brainstorm 2026-05-15)

#### 1. Tech stack

**FastAPI + Next.js 14+ App Router (TypeScript) + shadcn/ui + Tailwind CSS + AG Grid Community + TradingView lightweight-charts + ECharts (auxiliary) + TanStack Query + Zustand.**

Rejected:
- **Streamlit** — page-as-function model + opinionated chrome cannot reach the stated bar.
- **FastAPI + HTMX/Alpine** — minimal-dependency option; rejected because financial-grade interactive charts, dense tables (AG Grid–class), dockable panels, command palettes, and design systems all live in the React/Vue ecosystem; HTMX would cap the workbench at ~70% of the stated bar and force progressive rewriting later.
- **FastAPI + SvelteKit** — viable but financial component ecosystem (especially AG Grid) is React-first; not worth deviating from the mainstream path.
- **Tauri / Electron desktop wrapping** — adds packaging burden without buying anything for single-user single-machine local-only use; reachable later if desired.

Project-culture impact: `trade/` remains pure stdlib. The workbench lives in a sibling `workbench/` (or equivalent) directory with its own dependency graph (Python: FastAPI + Pydantic; Node: Next.js + npm). Audit-able-by-default rule: `shadcn/ui` was chosen over MUI / Antd because it follows the "own the source" model — components are copied into the repo, not imported from a black box.

#### 2. PRD §7 / §12 amendment timing

Amend at **B019 done wrap-up** (Path B19-DW), not now and not as a B020 spec preamble. Rationale:

- B019 is in `verifying`; planner is idle. The PRD is not on any reader's hot path in the next 1–3 days.
- Done wrap-up is the natural consolidation point. Bundling the PRD revision with B019 closure + backlog re-prioritization (BL-B011-S2 / D1 / D2 priorities re-evaluated against the new workbench plan) + B020 launch keeps the change set coherent.
- Avoids two separate documentation PRs.

The amendment must touch:

- **§7** (前端边界): rewrite the "MVP 不实现正式前端 dashboard" passage. The four original reasons either no longer hold (1–3) or are mitigated by the Phase split (4). New text must explicitly identify the workbench as an MVP completion path.
- **§12** (里程碑): the "B009 Broker Adapter Paper" row is replaced by "B020 Research Workbench (Phase 1)" + "B021 Workbench Phase 2 (manual execution + journal)". The original Broker-Adapter-Paper milestone is footnoted as moved to PRD §5 non-MVP scope (auto broker integration permanently deferred).
- Optionally **§3 / §4** may add a one-line statement that the workbench is the canonical user surface and the CLI remains supported for automation and CI.

#### 3. Phase 1 scope (B020)

**7 pages, full read-mostly with a minimum-necessary set of write actions.**

Pages: Home / Strategies / Backtest viewer / Reports / Recommendations / Snapshots / Backlog.

Write actions: snapshot refresh (calls `scripts.refresh_public_snapshot`), backlog CRUD (writes `backlog.json` + auto-commits), trigger backtest (runs `trade.master.run_backtest()` and stores result), generate target positions (runs `scripts.generate_target_positions` and exports Markdown — does **not** place orders).

Deferred to Phase 2 (B021):

- Execution panel (diff / ticket UI / fill upload)
- Account state + Journal viewer
- Manual execution UX brainstorm

Deferred to Phase 3+ (B022 or later, possibly never):

- Multi-panel dockable layouts
- Saved view / dashboard layout persistence
- Keyboard command palette (cmd-K)
- Dark/light theme toggle (Phase 1 ships dark by default — consistent with financial-tool convention)
- i18n
- Real-time data streams (WebSocket / SSE)
- Desktop packaging (Tauri)

Estimated Phase 1 scope: ~25–30 features across 5–6 weeks.

#### 4. Chart interactivity + export depth

**Level 2 standard.**

In scope for Phase 1: zoom / pan / crosshair tooltip (lightweight-charts default), multi-series overlay (e.g., B013 vs static 60/40 vs SPY on the same chart), brush selection for sub-window analysis, legend-driven overlay add/remove, chart PNG export, table CSV export (AG Grid built-in), Markdown report export (already exists in repo).

Out of scope for Phase 1:

- Multi-panel time-axis linking (two charts share a synced cursor)
- Drawing tools (trend lines, Fibonacci) — irrelevant for low-frequency ETF rotation research
- PDF report assembly (would require Puppeteer headless or react-pdf — 1–2 weeks of pure engineering plus visual regression tests; browser print-to-PDF is a free fallback)
- Self-contained HTML snapshots (niche value — a PNG + Markdown email already covers the "share a report with someone" use case)

If the user later needs PDF assembly, the trigger conditions would be: periodic submission to an accountant / financial advisor, a multi-account family-explanation flow, or formal reconciliation with broker statements. None of those scenarios are on the current roadmap.

## Consequences

### Positive

- The user gets a workbench experience that matches the stated bar.
- All MVP code paths (backtest, attribution, sweep, recommendations) become discoverable and explorable through one UI surface.
- Manual execution risk (the "you must remember to run the right CLI in the right order" failure mode) is reduced once Phase 2 ships.
- Architectural ceiling is high: real-time data, multi-panel layouts, command palettes, and desktop packaging are all reachable later without a rewrite.

### Negative

- MVP completion (PRD §10 / §11 / §12) is delayed by ~2–3 months relative to the CLI route.
- The project takes on Node / npm / TypeScript as first-class concerns; CI must add Node-side jobs (Vitest, Playwright, build).
- Maintenance surface grows: `npm audit`, framework upgrades (Next.js, React, shadcn/ui), and visual regression tests all become recurring costs.
- The audit-able / minimum-dependency culture of `trade/` is preserved by isolation (`workbench/` is its own dependency graph) but the project as a whole is no longer "Python-only" or "stdlib-only."

### Neutral / mitigations

- Single-user / single-machine / local-only constraint is preserved. The workbench MUST bind to localhost and MUST NOT introduce auth, broker SDKs, or live API endpoints.
- All hard guards from `docs/engineering/no-live-safety-guards.md` and the framework v0.9.21 #1 real-data reverify rule continue to apply.
- The CLI surface remains supported. Every UI action must be backed by an equivalent CLI script so automation, CI, and headless reproducibility paths are uninterrupted.

## Implementation order

1. **B019** finishes (in `verifying` as of this ADR; awaiting Codex F002 verdict and conditional Stage 2).
2. **B019 done wrap-up** (planner session): close B019 properly, amend PRD §7 / §12 per this ADR, re-prioritize backlog (BL-B011-S2 / D1 / D2 likely move down or stay where they are — to be revisited with workbench in mind), and open B020.
3. **B020 spec drafting**: brainstorming output is mostly captured here; spec drafting will turn the 4 sub-decisions into concrete features (~25–30 features), align hard boundaries (localhost-only, no auth, sibling `workbench/` directory), and define the Phase 1 acceptance gates.
4. **B020 execution**: ~5–6 weeks across multiple Generator + Codex passes.
5. **B021 spec drafting**: separate brainstorm for manual execution UX (diff / ticket / fill) before locking the Phase 2 scope. Execution-layer schema stabilization is part of Phase 2.

## Cross-references

- `docs/prd/mvp-prd.md` (to be amended at B019 done wrap-up)
- `docs/specs/B012-paper-trading-prep-mvp-spec.md` (existing `BrokerAdapter` ABC — unchanged; remains the future escape hatch if auto execution is ever revisited)
- `docs/engineering/no-live-safety-guards.md` (unchanged; workbench inherits all guards)
- `docs/engineering/testing-and-fixture-policy.md` (workbench L1 tests remain fixture-first; new policy on Node-side tests will be added as part of B020)
- `framework/CHANGELOG.md` v0.9.21 #1 — fixture-vs-real signal reversal rule applies equally to anything the workbench renders

---

## Addendum 2026-05-15 — Cloud Deploy Pivot + Renumber

### Context

After the original ADR was written and B020 (Workbench Phase 1) was first specced as a localhost-only application, the user surfaced two further requirements during B019 done wrap-up planning:

1. **CI/CD/E2E infrastructure should be established before frontend feature work begins.** The original B020 F001 lumped scaffolding + CI + safety guards + template clone + financial pre-config into one feature, which the user rejected as too monolithic. They asked for an independent infrastructure batch.
2. **The workbench is to be deployed to the user's existing GCP VM** (which already hosts the user's `aigcgateway` production service), accessible from multiple devices (laptop / phone / iPad) at `https://trade.guangai.ai`. This contradicts the original "localhost only" assumption.

### Updated batch sequence

Replaces the original Implementation order list:

1. **B019** done (signed off `docs/test-reports/B019-retune-signoff-2026-05-15.md`).
2. **B019 done wrap-up** (this session): PRD §7/§12 amendment, framework v0.9.22 sink (T+1 headroom), backlog re-prioritization (BL-B011-S2 medium → high), workbench-template-research integration (commit `eb42730`), then this addendum + new B020 / B021 specs.
3. **B020 Dev Infrastructure** (5 features, ~1.5 weeks): workbench skeleton + Python/Node toolchain bootstrap + CI workflows (workbench-backend + workbench-frontend) + testing strategy + safety guard scaffolding + OpenAPI ↔ TypeScript pipeline + dev docs + Codex L1 verification.
4. **B021 Cloud Deploy & Auth** (6 features, ~2-3 weeks): Google OAuth integration (NextAuth + backend session validation + email allowlist) + SQLite + Alembic migrations + Repository data layer abstraction + Dockerfile + systemd unit + nginx vhost (reusing aigcgateway's nginx) + cert provisioning for trade.guangai.ai + CI/CD pipeline (GitHub Actions push → SSH deploy → health check → symlink rollback) + backup automation (SQLite snapshot → GCS) + observability (healthcheck + structured log) + Codex L1+L2 verification.
5. **B022 Workbench Phase 1** (was B020 in the original ADR; renamed to B022, spec at `docs/specs/B022-workbench-phase1-spec.md`, content pending revision after B021 lands to wire OAuth + SQLite + Repository layer).
6. **B023 Workbench Phase 2** (was B021 in the original ADR; manual execution UI: position diff / order ticket / fill journal).

### Updated tech stack additions (replaces original §决策 1 partially)

The frontend / shadcn-ui / chart / table choices in the original ADR §决策 1 are unchanged. The cloud architecture adds:

- **Hosting:** GCP VM (existing, shared with aigcgateway). Resource quotas via systemd `CPUQuota=200%` + `MemoryMax=2G` to fence workbench from aigcgateway.
- **Reverse proxy:** nginx (existing, used by aigcgateway). New server block for `trade.guangai.ai`. Cert via certbot (Let's Encrypt).
- **Database:** SQLite + persistent disk at `/var/lib/workbench/workbench.db`. Schema managed by Alembic. Repository pattern in backend.
- **Authentication:** Google OAuth via NextAuth.js (frontend) + backend session validation. Single-email allowlist via env var. No registration UI — the user is the only legitimate user.
- **Backup:** SQLite snapshot via cron / systemd timer → GCS bucket (gzip + 30 daily + 12 monthly retention + restore script).
- **CI/CD:** GitHub Actions on push to main runs tests → builds artifacts → SSH-deploys to VM → health check → symlink rollback on failure. SSH key in GitHub Secrets.
- **Observability:** healthcheck endpoint + structured logging (request_id + user_id) + uvicorn access log + optional Sentry (free tier).

### Hard boundaries that **stay** unchanged

- Single user (single email in OAuth allowlist). Multi-user remains non-MVP per PRD §5.
- No broker SDK imports.
- No paper / live API URL strings.
- No order placement (Recommendations exports Markdown checklist only).
- Research-only disclaimer on every page.
- Auto broker / auto trading / AI-decision automation forbidden.
- `trade/` package remains pure stdlib.

### Hard boundaries that **change**

- "Localhost only" → "trade.guangai.ai with OAuth-gated single-user access; no public unauth endpoint."
- "No auth" → "Google OAuth required for all routes except `/api/health` and `/api/auth/*`."
- "No secret" → "Secrets managed via env var loaded from systemd unit's EnvironmentFile or GCP Secret Manager: GOOGLE_OAUTH_CLIENT_SECRET, NEXTAUTH_SECRET, ALLOWED_USER_EMAIL, optional SENTRY_DSN. Single-source loaded once at boot; never logged."
- "File-based data" → "SQLite + Repository layer; legacy file reads (e.g. `accounts/me.json`) remain as bootstrap-only fallback for first-run UX, then migrated into DB."

### User-action prerequisites for B021

Before B021 F001 can land, the user must complete (~30-60 minutes total):

1. Google Cloud Console: create OAuth 2.0 client (Web app), redirect URI `https://trade.guangai.ai/api/auth/callback/google`, hand off `client_id` + `client_secret`.
2. DNS: add `trade.guangai.ai` A record pointing at VM public IP.
3. VM SSH: create `deploy` user, add `/var/lib/workbench/` directory with deploy-user write perm, install GitHub Actions deploy SSH public key into `~/.ssh/authorized_keys`.
4. GCS: create backup bucket (region same as VM).
5. GitHub Secrets: upload SSH private key, OAuth client secret, NextAuth secret (random 32-byte value generated via `openssl rand -hex 32`), allowlist email.

These will be itemized in B021 F001 spec.

### Cross-references update

- `docs/prd/mvp-prd.md` §7 / §8 / §12: requires re-amendment in this same session to reflect cloud deployment.
- `docs/specs/B020-dev-infrastructure-spec.md`: new spec drafted in this same session.
- `docs/specs/B022-workbench-phase1-spec.md`: renamed from B020; content pending revision after B021 lands.

_Disclaimer: research-only; never authorizes paper or live trading._
