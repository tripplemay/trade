# B023 Workbench Phase 2 — Manual Execution UI Spec

## Background

B022 (`docs/test-reports/B022-workbench-phase1-signoff-2026-05-18.md`) shipped the read-mostly research workbench at `https://trade.guangai.ai`: 7 pages (Home / Strategies / Backtest / Reports / Recommendations / Snapshots / Backlog) on top of B020's dev tooling + B021's cloud + OAuth + SQLite/Alembic/Repository foundation. B022 deliberately stopped at "view recommendations + export a Markdown ticket"; actually closing the loop with manual broker execution + post-trade fill recording was deferred.

B023 closes that loop. It is the canonical end of MVP per ADR `docs/adr/2026-05-15-workbench-direction.md` (cloud addendum) — after B023 the workbench supports the monthly rebalance workflow end-to-end with the user as the order-execution layer:

1. Open Recommendations → see target portfolio diff vs current account state
2. Generate Order Ticket → see line-by-line buy/sell checklist with limit hints + tax/wash-sale flags
3. User manually executes in their broker app (IBKR / Schwab / etc. — NOT in workbench)
4. Upload Fills (CSV from broker or manual entry per line)
5. Workbench reconciles fills → updates account state → records slippage → ready for next cycle

The hard boundary continues: **B023 does not place orders, does not connect to any broker, does not hold broker credentials, does not simulate fills.** The user is the executor. Workbench is the workflow / record-keeping / analytics layer around manual execution.

## Goal

Ship the manual-execution workflow UI on top of the B022 Workbench Phase 1 + B021 cloud foundation:

- **Position diff page** — given current account state + target portfolio, show signed dollar/share/weight diff per holding + rationale why each is changing.
- **Order ticket generation** — render the diff as a human-readable checklist (one row per trade): action / symbol / shares / limit-price hint / reference close / wash-sale flag / tax-lot hint / one-line reason. Export as Markdown, downloadable, also persistable in the DB.
- **Fill journal** — user uploads a fills CSV (broker export) OR enters fills manually after executing. Each fill is one row: order_seq, symbol, side, shares, fill_price, commission, fees, filled_at. Journal is append-only.
- **Reconciliation** — match fills to ticket rows, compute realized slippage (fill_price - reference_close), update account state to reflect new positions, archive ticket as "executed" with the journal back-reference.
- **Account state edit UI** — was deferred from B022 (Recommendations page expected user to edit `accounts/me.json` manually). B023 adds a UI to edit account JSON safely via form + DB persistence.
- **Journal history page** — past tickets + their fills + slippage analytics (avg slippage in bps per month, trend, outliers).
- **Risk panel / kill-switch alert UI** — show master DD vs kill-switch threshold; if exceeded, ticket generation displays a defensive-allocation alternative in addition to the normal trade ticket; user explicitly chooses which to follow.

After B023 done, PRD §10 / §11 / §12 success criteria are 100% met for a single-user manual-execution workbench. MVP complete.

## Hard Decisions

### Boundary (non-negotiable — inherited + extended)

| Item | Rule |
|---|---|
| Broker integration | **Forbidden.** No SDK import, no API URL, no credential. The `BrokerAdapter` ABC from B012 stays an unwired abstraction. |
| Auto-execution | **Forbidden.** No button labelled "execute", "place order", "send to broker". Buttons say "export ticket", "record fills", "reconcile". |
| Paper trading | **Forbidden.** B023 ships the same workflow user would use against a real broker; the project simply never connects. |
| Multi-user | Single email allowlist continues (B021). No registration UI. |
| Cloud expansion | No Cloud SQL / Postgres / multi-region. SQLite + GCS backup continues. |

### Data model extensions (F001)

Three new tables in the existing `/var/lib/workbench/db/workbench.db` via Alembic migration:

| Table | Columns | Purpose |
|---|---|---|
| `order_ticket` | id PK, ticket_date, snapshot_id, target_positions_id (FK to TargetPositions output), markdown_path, status (`generated` / `executed` / `voided`), created_at, executed_at | One row per ticket generation. Status transitions: `generated` → `executed` when reconciled, `voided` if user decides not to trade. |
| `fill_journal_entry` | id PK, ticket_id FK, order_seq, symbol, side (`buy`/`sell`), shares, fill_price, commission, fees, currency, filled_at, source (`csv_upload` / `manual_entry`), notes, created_at | Append-only. Per-fill record. Reconciliation matches by (ticket_id, order_seq) or (ticket_id, symbol+side). |
| `account_snapshot` | id PK, snapshot_at, cash, base_currency, positions (JSON: `[{symbol, shares, avg_cost}]`), source (`bootstrap` / `ui_edit` / `fill_reconcile`), created_at | Each material account state change creates one snapshot. Recommendations page uses `latest()`. Slippage analytics joins through here. |

All three tables are auth-gated via existing `require_authenticated_user` dependency. Repository layer follows B021 F002 pattern (`base.py` + per-model thin wrappers).

### Workflow state machine (F003 + F004 + F005 + F006)

```
[ Account snapshot (latest) ]
        |
        v
[ Recommendations page (B022 F010 + diff details from B023 F003) ]
        |
        | "Generate Order Ticket"
        v
[ order_ticket row (status=generated) + Markdown file ]
        |
        | (user manually executes in broker app, offline)
        v
[ Fills CSV / manual entry (B023 F005) ]
        |
        | "Reconcile fills"
        v
[ fill_journal_entry rows + new account_snapshot (source=fill_reconcile) ]
        |
        | (status flips generated → executed)
        v
[ Journal history (B023 F006) shows past tickets + slippage ]
```

Each transition is **user-driven** (button click). No automatic state change.

### Same-origin + auth + Repository (all per v0.9.24 #3 + v0.9.25 #1a-d)

- All frontend fetch uses `/api/*` same-origin paths.
- All new backend routes behind `require_authenticated_user`.
- All reads via Repository; no direct file mutation (account.json + journal both DB-backed; ticket Markdown file is artifact, DB row is canonical).
- Alembic migration `0002_b023_execution_workflow.py` adds the 3 tables. F001 includes deploy.sh schema-assert update to include the new tables (per v0.9.25 #1b).
- workbench-deploy.yml stage step continues to ship `docs/test-reports` + `docs/specs` (per v0.9.25 #1c). B023 adds `docs/runs` to the staged content (Recommendations export wrote there during B022; B023 reads back for journal history).

### CSV import format

Standardize on a minimal CSV schema that most broker exports can either produce directly or be coaxed into:

```csv
order_seq,symbol,side,shares,fill_price,commission,fees,currency,filled_at
1,SPY,buy,72,501.85,0.00,0.00,USD,2026-05-30T13:31:42Z
2,IEF,sell,45,94.18,0.00,0.00,USD,2026-05-30T13:32:15Z
```

- `order_seq` matches the row number in the ticket Markdown (1-indexed).
- `filled_at` is ISO 8601 UTC.
- `fill_price` is post-fees execution price.
- `commission` + `fees` may be 0 for zero-commission brokers (Schwab US ETFs).
- Missing rows in CSV mean "didn't fill that line"; the reconciler treats them as `partial` and prompts the user to record manually if intentional.

F005 includes a 1-page CSV-format-help doc + 3 example CSV fixtures (Schwab / IBKR / generic).

### Risk panel (F007)

Surface 3 risk signals on the Recommendations page header:

1. **Master DD vs kill-switch** (15% per B011 spec). If `current_master_dd >= 0.15`, page shows a banner with the alternative "defensive allocation" ticket (move everything to SGOV/defensive sleeve). User explicitly picks which ticket to export.
2. **Per-sleeve drawdown** breakdown.
3. **Recent slippage trend** (rolling 3-month) — if > 30 bps consecutive months, show advisory to switch from Market to Limit orders or change cadence.

These are informational; B023 does not auto-disable trade ticket generation. User decides.

## Architecture

Builds entirely on B021 + B022:

- Backend: extends `workbench_api/db/models/` + `repositories/` with 3 new models. New route module `workbench_api/routes/execution.py` exposes the ticket / fill / reconcile / account-snapshot endpoints. Uses existing `auth/dependency.py` + `db/session.py`.
- Frontend: 4 new pages under `(protected)/`: `execution/position-diff`, `execution/ticket`, `execution/fills`, `execution/journal-history`, `execution/account`. Reuse F005 DataTable + F004 charts. Use shadcn Dialog + Form for upload + edit modals.
- Deploy: same workbench-deploy.yml chain (no new workflow). Alembic migration auto-runs on deploy via existing deploy.sh step (now with v0.9.25 #1a env-source + #1b schema-assert).

### Request lifecycle (key flow — ticket → fills → reconcile)

```
1. POST /api/recommendations/generate-ticket
   - auth-gated; reads latest account_snapshot + latest target_positions
   - inserts order_ticket row (status=generated)
   - writes Markdown to docs/runs/<date>/order-ticket-<ticket_id>.md
   - returns {ticket_id, markdown_path}

2. (User executes in broker app, manually)

3. POST /api/execution/fills (multipart CSV) or POST /api/execution/fills/manual (JSON per-row)
   - auth-gated; validates against ticket_id; inserts fill_journal_entry rows
   - returns {fill_ids, ticket_id}

4. POST /api/execution/reconcile/{ticket_id}
   - auth-gated; matches fills to ticket; computes slippage
   - creates new account_snapshot (source=fill_reconcile, positions = previous + signed shares from fills)
   - updates order_ticket.status=executed, executed_at=now
   - returns {snapshot_id, slippage_summary, unmatched_lines}

5. GET /api/execution/journal-history?since=<date>
   - auth-gated; returns past tickets + fills + slippage analytics
```

## Feature Requirements

### F001 — DB schema extension + Alembic migration + Repository

Executor: generator.

Add 3 new SQLAlchemy models (`OrderTicket`, `FillJournalEntry`, `AccountSnapshot`) under `workbench/backend/workbench_api/db/models/`. Add matching repository classes following B021 F002 pattern (`base.py` generic + per-model with `latest()`, `list_by_ticket()`, `reconcile()` helpers). New Alembic migration `versions/0002_b023_execution_workflow.py` creates the 3 tables + indexes (ticket_id on fills, snapshot_at desc on snapshots).

**v0.9.25 #1b enforcement:** update `workbench/deploy/scripts/deploy.sh` schema-assert `required` set to `{"account", "backlog_entry", "snapshot_meta", "order_ticket", "fill_journal_entry", "account_snapshot"}` (3 old + 3 new).

Acceptance:

1. `alembic upgrade head` on fresh DB creates all 6 tables; running again is no-op (idempotent).
2. Repository round-trip pytest for each new model (create / read / update / delete + per-model bespoke helpers).
3. `WORKBENCH_DB_URL=sqlite:///./workbench-dev.db alembic upgrade head` works in dev.
4. deploy.sh schema-assert lists all 6 tables; intentional missing-table commit triggers fail.
5. safety regression test (no psycopg2 / mysqlclient / pymongo / broker SDK) continues green.
6. backend pytest + ruff + mypy all clean.

### F002 — Position diff page + Account state edit UI

Executor: generator.

Backend:
- `GET /api/execution/position-diff?as_of=<date>` returns `{current: AccountSnapshot, target: TargetPositions, diff: [{symbol, current_shares, target_shares, delta_shares, current_weight, target_weight, delta_weight, delta_dollar, reason}], unmatched: [{...}]}`. `delta_*` is signed (positive = buy, negative = sell). `reason` from existing strategy logic in `trade/`.
- `GET /api/execution/account/latest` returns the latest `AccountSnapshot` row.
- `PUT /api/execution/account` accepts `{cash, base_currency, positions: [...]}`; inserts new `AccountSnapshot` row with `source=ui_edit`.

Frontend:
- New page `(protected)/execution/position-diff/page.tsx`: AllocationBar comparing current vs target + per-row diff DataTable (signed delta with color: green for buy / red for sell, using `--color-up` / `--color-down` tokens from B022 F001).
- New page `(protected)/execution/account/page.tsx`: form to edit account (cash + per-symbol shares + avg_cost); on submit calls PUT and shows toast.

Acceptance:

1. Position diff page renders correctly with seeded fixture account + fixture target portfolio (no real OAuth account needed for L1).
2. Diff shows correct signs (delta_shares > 0 when target > current).
3. Account edit form validates (weights sum ≤ 1.0, cash ≥ 0, no duplicate symbols); on submit inserts new snapshot and Recommendations / Position-diff pages immediately reflect the new state.
4. CSV export of diff table works.
5. Vitest + Playwright smoke + httpx contract.

### F003 — Order ticket generation + viewer + Markdown export

Executor: generator.

Backend:
- `POST /api/execution/tickets` generates a new ticket from current diff (consumes `/api/execution/position-diff` internally). Writes Markdown to `docs/runs/<YYYY-MM-DD>/order-ticket-<ticket_id>.md` (already shipped in release tarball per v0.9.25 #1c). Inserts `order_ticket` row.
- `GET /api/execution/tickets` lists tickets with pagination.
- `GET /api/execution/tickets/{ticket_id}` returns full ticket (DB row + parsed Markdown).
- `POST /api/execution/tickets/{ticket_id}/void` flips status to `voided` (user decides not to trade).

Markdown ticket template (auto-rendered by backend; user never edits the file):

```markdown
# Order Ticket — <ticket_date> (T+1 execution day: <T+1>)

> ⚠️ Manual review checklist. The system does NOT place orders. You are the executor.
> Reference prices = <snapshot_date> close; place LIMIT orders only.

## Account snapshot
- Cash before trades: $<cash>
- Total NAV: $<nav>

## Trades to place (<N> lines, T+1)
| # | Action | Symbol | Shares | Reason | Limit hint | Reference close |

## Tax / wash-sale flags
- <if any>

## After execution checklist
- [ ] Record actual fills in workbench's Fill Journal (page link)
- [ ] Or upload CSV from broker

_Disclaimer: research-only; this is a manual review checklist, not a trading instruction._
```

Frontend:
- New page `(protected)/execution/ticket/page.tsx`: shows latest ticket + "Generate new ticket" + "Void" buttons + Markdown preview + "Download Markdown" button.
- Ticket viewer subpage `(protected)/execution/ticket/[ticket_id]/page.tsx`: read-only render of past ticket.

Acceptance:

1. Generate-ticket end-to-end produces both DB row + Markdown file; Markdown asserts literal disclaimer string.
2. List + detail viewer works for ≥ 3 historical tickets (seeded).
3. Void changes status; voided tickets cannot be reconciled later.
4. Frontend regression: any button labelled "execute" / "place order" / "send to broker" is forbidden (Vitest grep + Playwright assert).
5. Same-origin path used; no `127.0.0.1` in build artifact (v0.9.24 #3 regression).

### F004 — Fill journal upload (CSV + manual entry)

Executor: generator.

Backend:
- `POST /api/execution/fills` accepts multipart CSV file or JSON `{ticket_id, fills: [...]}`. Validates against ticket (every fill must have matching `order_seq` in ticket OR be `--unmatched` flagged). Inserts `fill_journal_entry` rows.
- `GET /api/execution/fills?ticket_id=<id>` returns fills for a ticket.

CSV parsing:
- Standard format documented in F005 (CSV schema). Backend uses `csv` stdlib + Pydantic per-row validation.
- Errors return 400 with row-level details (`{row: 3, error: "fill_price not a number"}`).

Frontend:
- New page `(protected)/execution/fills/page.tsx`: upload CSV (shadcn `<input type=file>`) + manual entry table for ad-hoc fills (one row per fill, validated client-side).
- After upload, show "preview" view: each fill matched against ticket row; user confirms before commit.

Acceptance:

1. Upload 3 fixture CSV files (Schwab / IBKR / generic format); each parses correctly with `≤ 5 LOC` adapter glue per broker.
2. Manual entry validates client + server side (positive shares, valid date, known symbol from ticket).
3. Unmatched fills flag user prompt (does not auto-reject).
4. Vitest + Playwright + backend contract tests.

### F005 — Reconciliation + journal history + slippage analytics

Executor: generator.

Backend:
- `POST /api/execution/reconcile/{ticket_id}`: matches fills, computes slippage, inserts new `account_snapshot` (source=fill_reconcile), flips ticket status.
- `GET /api/execution/journal-history?since=<date>` returns past tickets + their fills + slippage summary (per-ticket avg bps + count of fills).
- `GET /api/execution/slippage-analytics?window=<3m|6m|1y>`: rolling avg slippage in bps + outliers + trend direction.

Frontend:
- New page `(protected)/execution/journal-history/page.tsx`: DataTable of tickets with expand-row to see fills + slippage; sortable / filterable / CSV export.
- Per-ticket detail: AllocationBar of intended vs realized + slippage chart (lightweight-charts area).

Acceptance:

1. Reconcile end-to-end on fixture ticket+fills: inserts correct new snapshot + slippage; idempotent (running twice doesn't dupe snapshots).
2. Journal history renders 12 months of fixture data; sortable.
3. Slippage analytics correctly computes bps = `(fill_price - reference_close) / reference_close * 10000` signed per trade direction.
4. Vitest + Playwright + contract.

### F006 — Risk panel + kill-switch alert UI

Executor: generator.

Backend:
- `GET /api/execution/risk-panel` returns `{master_dd, kill_switch_threshold, kill_switch_triggered: bool, per_sleeve_dd: {...}, slippage_trend_3m_bps}`.
- If `kill_switch_triggered`, also returns `alternative_defensive_ticket` (a separately computed ticket that moves everything to defensive sleeve).

Frontend:
- Risk panel banner on Recommendations page header (B022 F010 extension): green if all OK, yellow if any per-sleeve DD > 8%, red if kill-switch triggered.
- If red: page shows side-by-side "normal ticket" vs "defensive ticket" + radio button for user to choose which to generate.

Acceptance:

1. Risk panel renders correctly for: (a) all-OK fixture, (b) yellow per-sleeve DD, (c) red kill-switch triggered (with alternative defensive ticket visible).
2. Generate-ticket honors user's radio selection.
3. Vitest + Playwright.

### F007 — Docs + screenshots + workflow runbook

Executor: generator.

- `docs/dev/workbench-architecture.md` updated with B023 5 new pages + workflow state machine + DB schema diagram.
- `docs/dev/workbench-manual-execution-runbook.md` new: end-to-end user workflow (open Recommendations → generate ticket → execute in broker → upload fills → reconcile → see slippage). Includes 3 CSV format examples (Schwab / IBKR / generic).
- Update `docs/screenshots/` with B023 5 new pages.
- `workbench/README.md` reference docs section updated.

Acceptance:

1. Runbook is a single-user can-follow doc: each step has command / click instruction / expected result.
2. Screenshots updated.
3. CLAUDE.md reference-docs section updated.

### F008 — Codex L1 + L2 verification + workbench Phase 2 signoff

Executor: codex.

L1 checklist (in CI):

1. `pytest workbench/backend/tests/ -q` green; ruff + mypy clean.
2. `npm test --prefix workbench/frontend` green; lint + typecheck clean.
3. Playwright E2E walks all 5 new pages (position-diff / ticket / fills / journal-history / account); asserts disclaimer visible on each, asserts no `127.0.0.1` in build artifact (v0.9.24 #3 regression).
4. Safety regression: no broker SDK import, no paper / live URL strings, no button labelled "execute" / "place order" / "send to broker" in any component.
5. `npm audit --omit=dev --audit-level=high` clean (per v0.9.25 #3a).
6. deploy.sh schema-assert lists 6 tables; intentional missing-table commit fails CI.

L2 checklist (on production trade.guangai.ai, **per v0.9.25 #1d — must include real read + real write**):

7. Browser OAuth happy path; land on `/` (Home unchanged).
8. Navigate to `/execution/position-diff`: shows diff between current account + target (seeded test account).
9. Navigate to `/execution/account`, edit cash by +$1000, submit, refresh — new value persists.
10. Navigate to `/execution/ticket`, click Generate; Markdown file appears in `docs/runs/<today>/`; DB row inserted.
11. Navigate to `/execution/fills`, upload 1 fixture CSV (Schwab format), confirm preview, commit.
12. Navigate to ticket, click Reconcile; status flips to `executed`; new account snapshot appears in account viewer.
13. Navigate to `/execution/journal-history`; the just-reconciled ticket shows up with slippage value.
14. Risk panel: confirm green badge for normal case.
15. `/api/health` still returns 200 with 6 obs fields including `db_connectivity=ok`.
16. systemctl quota knobs + neighbor services (nginx / pm2 aigcgateway / apify-kol) unaffected.
17. Production / HEAD equivalence per signoff template v0.9.25 §"Production / HEAD 等价性"; deploy must be triggered if diff contains workbench/** changes.
18. `/api/debug/recent-errors` returns `count=0` after entire flow (per v0.9.25 #3c).

Codex writes `docs/test-reports/B023-workbench-phase2-signoff-2026-MM-DD.md` using updated `framework/templates/signoff-report.md` (including new §"Production / HEAD 等价性"). Updates progress.json status → done, docs.signoff set, evaluator_feedback summarizes both L1 + L2.

## Out of Scope

- **Broker integration (paper or live).** Permanent; B012's BrokerAdapter ABC stays unwired. PRD §5.
- **Auto-execution / scheduled trades.** User remains the executor.
- **Multi-user, registration, billing.** Single allowlist user.
- **Cloud SQL / Postgres / multi-region.** SQLite + GCS continues.
- **Tax-lot optimization / tax-loss harvesting algorithms.** Wash-sale flag is heuristic only (lookback for same-symbol buy in last 30 days). Sophisticated tax optimization is post-MVP.
- **Real-time price feeds.** Limit-price hints in ticket use snapshot close + a configurable buffer; no live quote API.
- **Mobile-first responsive design.** Workbench is desktop-first; mobile usable but not optimized.
- **Backtest replay against actual fills.** Comparison of "what backtest predicted" vs "what actually happened" is a useful post-MVP analytics batch.
- **Account aggregation across brokers.** Single logical account state.
- **Mass-uploaded historical fills migration.** B023 ships forward-going only; if user has months of past trades to import, that's a separate one-off batch.

## Acceptance

Batch is **done** when:

1. F001 — F007 all green on `main`; CI (workbench-backend + workbench-frontend + workbench-deploy) all green.
2. F008 Codex L1 + L2 verification: all 18 checklist items pass; signoff written using updated template (with §Production/HEAD 等价性 filled).
3. `progress.json.status = done`; `docs.signoff` populated.
4. Production https://trade.guangai.ai shows 5 new execution pages; OAuth gating + DB persistence + Markdown ticket export all live; backup + observability continue working unchanged.
5. No new framework violations: same-origin paths in build artifact, no broker SDK, no execution buttons, npm audit clean, deploy.sh schema-assert covers 6 tables, v0.9.25 #3c debug endpoint returns count=0 after exercising every new write path.
6. MVP per PRD §10 / §11 / §12 substantively complete for single-user manual-execution workbench.

_Disclaimer: research-only; never authorizes paper or live trading._
