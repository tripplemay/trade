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

_Disclaimer: research-only; never authorizes paper or live trading._
