# Manual-execution runbook (B023 Phase 2)

This runbook walks one full monthly rebalance from the workbench's point
of view. The workbench is **research-only** — it records what you
plan to do and what you actually executed in your broker app; it never
sends an order. Every step below is user-driven.

If anything here disagrees with `docs/specs/B023-workbench-phase2-manual-execution-spec.md`
the spec wins.

## Prerequisites

- You are signed in at `https://trade.guangai.ai` with the allowlisted
  Google account (B021 OAuth).
- The DB has at least one `account_snapshot` row. Seed one via the
  Account page (`/execution/account`) before generating a ticket;
  `POST /api/execution/tickets` returns 409 otherwise.
- Your broker exports fills as CSV (Schwab / IBKR / a generic five-column
  shape — see §CSV formats below).

## End-to-end flow

```text
1. Recommendations  → review target portfolio + risk banner
2. Position diff    → see signed Δshares the workbench thinks you need
3. Ticket           → Generate (normal or defensive) → write Markdown
4. (You)            → place orders manually in your broker app
5. Fills            → upload CSV or hand-enter fills
6. Reconcile        → POST flips the ticket → executed + writes new snapshot
7. Journal history  → see slippage bps + trend + outliers
```

### Step 1 — Recommendations (`/recommendations`)

- Open the page. The risk banner sits at the top.
- **Green** state: master DD < 8%; proceed normally.
- **Yellow** state: any sleeve DD ≥ 8% advisory threshold; still
  proceed, but expect the journal to surface the drawdown.
- **Red** state: master DD ≥ 15% kill-switch threshold. The Ticket page
  will offer a normal-vs-defensive radio in step 3.
- Use the AllocationPie + AllocationBar to confirm the target weights
  match expectations. The existing "Export markdown ticket" button on
  this page is the B022 F010 surface; B023 ticket generation lives on
  the Ticket page (see step 3).

**Expected on the screen:** `data-testid="risk-banner"` with
`data-state` ∈ {green, yellow, red}; the 4-sleeve target positions
DataTable; the canonical research-only disclaimer card.

### Step 2 — Position diff (`/execution/position-diff`)

- The page joins the latest `account_snapshot` with the current target
  portfolio and shows the per-symbol signed Δ.
- **Green Δshares**: buy that many shares of the symbol.
- **Red Δshares**: sell that many shares.
- The "Unmatched targets" card flags target symbols with no cost-basis
  reference (the share-count math falls back to a placeholder). Treat
  those as "rebalance to weight, size by hand".
- Click "Export CSV" to capture the diff for later journaling.

**Expected on the screen:** `data-testid="position-diff-table-card"`
with at least the 4 sleeve symbols; signed Δ shares coloured via
`--color-up` / `--color-down`; equity line under the page header.

### Step 3 — Ticket (`/execution/ticket`)

- The same RiskBanner is reproduced at the top of this page.
- When the banner is **red**, the page also shows the
  `data-testid="ticket-mode-card"` with two radios:
  - **Normal** — follow the current Recommendations target.
  - **Defensive** — rotate 100% into the B011 defensive proxy (SGOV).
- The defensive radio is pre-selected on red so you have to actively
  opt back into the normal mode.
- Click **Generate {new|defensive} ticket**. The workbench:
  - Computes the diff (normal vs defensive based on the radio),
  - Writes `<runs_dir>/<ticket_date>/order-ticket-<id>.md`,
  - Inserts an `order_ticket` row (status=generated),
  - Returns the rendered Markdown body for preview.
- Click **Download Markdown** to save a local copy. The disclaimer
  literal is verbatim "research-only; this is a manual review
  checklist, not a trading instruction" — `tests/unit/test_tickets.py`
  pins this.
- If you change your mind, click **Void latest**. Voided tickets cannot
  be reconciled later (F005 returns 409); voided/executed tickets
  cannot be voided again either.

**Expected on the screen:** `data-testid="ticket-preview-card"` with
the Markdown body rendered through `MarkdownRenderer`; the history list
shows your newest ticket on top with status badge ∈ {generated,
executed, voided}.

### Step 4 — Place the trades in your broker (off-platform)

The workbench does not connect to a broker. Use the Markdown ticket as
your checklist:

- Place LIMIT orders only (the ticket says so explicitly).
- The "Reference close" column lists the snapshot price the diff used.
- For symbols flagged in the Unmatched section, you decide the share
  count yourself.

When fills land, your broker hands you a CSV (Schwab Order History,
IBKR Activity Statement, etc.). Keep it open for step 5.

### Step 5 — Fills (`/execution/fills`)

- Pick the ticket in the dropdown (auto-selected to the first
  generated ticket).
- **CSV upload path**: drop the broker file. The adapter (generic /
  Schwab / IBKR) is detected from header overlap. If your file is too
  far off-format, the backend returns 400 "Could not identify CSV
  adapter" with the header row in the message.
- **Manual entry path**: fill one row per execution and click Save
  fills. Client-side validation requires positive shares + positive
  price + symbol + ISO-8601 `filled_at`.
- **Unmatched fills**: if `order_seq` is null OR doesn't map to a
  known ticket line, the request 400s with a row-level error
  pointing you at the `allow_unmatched=true` checkbox. Toggling it
  on and re-submitting accepts the fills under
  `accepted_under_allow_unmatched=true`.
- The "Last insert" preview card shows each accepted row with the
  matched/unmatched flag; the persisted history table below shows
  every fill on this ticket.

**Acceptance pin:** every fixture CSV in `workbench/backend/tests/unit/test_fills.py`
parses with ≤ 5 LOC of broker-specific glue. The CSV adapter list
lives in `services/fills.py` (`_GENERIC_MAP` / `_SCHWAB_MAP` /
`_IBKR_MAP`).

### Step 6 — Reconcile (currently triggered manually via API)

The dedicated `/execution/reconcile` page is a backlog item; in B023
the reconcile step is called via the API or via the Journal-history
flow once an "execute reconcile" button lands. Today, with `curl`:

```bash
curl -X POST \
  -H "Cookie: authjs.session-token=<your-session>" \
  https://trade.guangai.ai/api/execution/reconcile/<ticket_id>
```

This:

- Computes signed slippage bps per fill (positive = unfavorable: paid
  more on a buy or received less on a sell).
- Builds a post-fill `account_snapshot` (weighted avg cost on buys,
  share depletion on sells, commissions/fees subtract cash) with
  `source=fill_reconcile`.
- Flips the ticket → `executed` and stamps `executed_at`.
- Returns the per-fill bps + aggregate summary + the new snapshot id.

Running the same call again returns `already_reconciled=true` without
inserting a second snapshot — F005 acceptance #2 pins this.

### Step 7 — Journal-history (`/execution/journal-history`)

- Three summary cards at the top: total ticket count, mean per-ticket
  avg bps, signed dollar slippage sum.
- Window selector (3m / 6m / 1y) re-fetches `/api/execution/slippage-analytics`
  with the new window.
- The monthly trend renders as an AllocationBar with one bar per
  month.
- The outliers list flags any ticket whose avg bps lives outside
  `max(30, 2 × |rolling_avg|)`.
- The AG Grid table at the bottom sorts/filters newest-first; click
  "Export CSV" for a spreadsheet.
- Each top-10 row links to the read-only ticket viewer
  (`/execution/ticket/<id>`).

## CSV formats

The workbench accepts three layouts; only the headers differ. Each
adapter normalises to the canonical `FillRowIn` shape (Pydantic) which
validates per-row.

### Generic format (recommended for new exports)

```csv
order_seq,symbol,side,shares,fill_price,commission,fees,currency,filled_at
1,SPY,buy,72,501.85,0.00,0.00,USD,2026-05-30T13:31:42Z
2,IEF,sell,45,94.18,0.50,0.10,USD,2026-05-30T13:32:15Z
```

- `order_seq` matches the 1-indexed row in the ticket Markdown.
- `side` is `buy` or `sell` (case-insensitive).
- `filled_at` must be ISO-8601 UTC.
- `currency` defaults to `USD` when missing.

### Schwab Order History export

```csv
#,Symbol,Action,Quantity,Price,Commission,"Fees & Taxes",Date
1,SPY,Bought,72,501.85,0.00,0.00,2026-05-30T13:31:42Z
2,IEF,Sold,45,94.18,0.50,0.10,2026-05-30T13:32:15Z
```

- "Bought" / "Sold" normalise to `buy` / `sell` via
  `services/fills._SIDE_NORMALISE`.
- Schwab does not include a `Currency` column; the adapter falls back
  to the `FillRowIn` default (`USD`).

### IBKR Flex / Activity Statement export

```csv
OrderID,Symbol,Buy/Sell,Quantity,TradePrice,IBCommission,Taxes,CurrencyPrimary,DateTime
1,SPY,BUY,72,501.85,0.00,0.00,USD,2026-05-30T13:31:42Z
2,IEF,SELL,45,94.18,0.50,0.10,USD,2026-05-30T13:32:15Z
```

- "BUY" / "SELL" pass through `_SIDE_NORMALISE`.
- `OrderID` maps to `order_seq`. For broker IDs that aren't 1-indexed
  integers, prefer the Generic format or manual entry.

If your broker is not in this list, dump a 4-column CSV in the Generic
shape and we'll accept it (adapter selection requires ≥ 4 canonical
columns to be present).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `POST /tickets` returns 409 "no snapshot" | Empty `account_snapshot` table | Visit `/execution/account`, fill in cash + positions, Save. |
| `POST /fills` returns 400 with `allow_unmatched` hint | A row has `order_seq=null` AND `allow_unmatched=false` | Tick the "Accept unmatched fills" checkbox on the Fills page and re-submit. |
| `POST /reconcile/{id}` returns 409 "voided" | Ticket was voided after fill upload | Generate a new ticket; reconcile the new one instead. |
| Risk banner shows red but no defensive ticket appears | `alternative_defensive_ticket` is null | The kill-switch did not trip — the banner is showing yellow advisory state. Re-check master DD vs the 15% threshold. |
| CSV upload returns 400 "Could not identify CSV adapter" | Headers don't overlap any adapter map by ≥ 4 columns | Re-export as the Generic format (top of this section). |
| Markdown file missing on `GET /tickets/{id}` | runs_dir was reset between deploys | Detail route degrades to "Markdown artifact at … is missing on disk; DB row preserved." Regenerate the ticket if you need the body. |

## What's deliberately not in this runbook

- Broker SDK / API keys — none exist in the workbench (F001 safety
  regression rejects every common SDK import).
- A "place orders" button — not now, not ever.
- Real-time market data — reference prices come from the cost basis on
  the prior snapshot. The slippage bps math is research-grade.
- Multi-user account state — single allowlisted email per B021.

Cross-references:

- Spec: `docs/specs/B023-workbench-phase2-manual-execution-spec.md`
- Architecture: `docs/dev/workbench-architecture.md`
- VM setup: `docs/dev/B021-vm-setup-runbook.md`
- Screenshot inventory: `docs/screenshots/README.md`
