# Workbench screenshots — B022 F013 + B023 F007 capture checklist

This directory holds PNG screenshots of the workbench's pages. The
acceptance text asks for one PNG per page, ≤300 KB each, named
consistently. B022 ships the 7 research-page gallery; B023 adds the 5
manual-execution pages + the red-state risk-banner shot.

## What to capture — B022 (7 research pages)

| Filename | Page | What it should show |
|---|---|---|
| `01-home.png` | `/` | 4 dashboard cards (NAV / DD / Kill-switch / Days-to-Rebalance) + Recent reports list + Action items panel. |
| `02-strategies.png` | `/strategies` | Sleeve DataTable with all 4 rows + per-strategy detail panel (config Card + Equity / Drawdown / Heatmap stacked + Spec/Code/Sweep buttons). |
| `03-backtest.png` | `/backtest` | ResizablePanel split: selector pane left + result stack right (Metrics card + Equity curve + Drawdown + Trades). After clicking Run. |
| `04-reports.png` | `/reports` | List of reports + click into one (e.g. B019 retune) showing the sweep matrix rendered as a sortable AG Grid (≥10-row swap). |
| `05-recommendations.png` | `/recommendations` | RiskBanner (green state) + Disclaimer Card + AllocationPie + AllocationBar + positions DataTable + gate panel + Export Markdown Ticket button. |
| `06-snapshots.png` | `/snapshots` | DataTable of snapshots + Refresh modal mid-stream (showing at least one stage event). |
| `07-backlog.png` | `/backlog` | DataTable filtered to `high` priority + the Add-entry Dialog open. |

## What to capture — B023 F007 (manual-execution pages)

| Filename | Page | What it should show |
|---|---|---|
| `08-position-diff.png` | `/execution/position-diff` | Current vs Target AllocationBar pair + 9-column diff DataTable with at least one positive Δ (green) and one negative Δ (red) row + Unmatched-targets card visible. Total equity line under the page header non-zero. |
| `09-ticket.png` | `/execution/ticket` | RiskBanner at the top + Generate / Void / Download buttons + Markdown preview rendered through MarkdownRenderer with the "Trades to place" + "After execution checklist" headings visible + History list with at least one prior generated ticket. |
| `10-ticket-defensive.png` | `/execution/ticket` (red state) | Risk banner in red state + `ticket-mode-card` with normal/defensive radios visible + defensive radio pre-selected + Generate button reading "Generate defensive ticket". |
| `11-fills.png` | `/execution/fills` | Ticket select + CSV upload card with `allow_unmatched` checkbox + manual-entry table with at least one valid row + preview card showing matched/unmatched flags + history table with at least one persisted fill. |
| `12-journal-history.png` | `/execution/journal-history` | 3 summary cards (count / avg bps / total dollar) + 3m window selector + AllocationBar monthly trend + outliers list + AG Grid table with sortable headers + top-10 ticket links. |
| `13-account-edit.png` | `/execution/account` | Form with cash + currency + dynamic positions rows (at least two rows) + Save / Reset buttons + state line showing "latest snapshot snap-… (ui_edit)". |

## Generator gap

Screenshot capture requires a browser session and is not something the
generator agent can produce automatically. Two practical paths:

1. **Operator capture (recommended).** Sign into `https://trade.guangai.ai`
   with the allowed Google account, walk the pages, and save each
   screenshot at 1440×900 (or device-default) into this directory. Use
   `pngquant --quality=70-90` if any file lands above the 300 KB budget.
2. **Codex L2 capture.** During F008 verification on the real VM, the
   evaluator can save Playwright trace screenshots from the authed
   project's runs (Playwright stores them under
   `workbench/frontend/test-results/`) and curate the ones that match
   the checklists above. For B023 F006 the red-state shot requires
   seeding two snapshots with ≥ 20% drawdown so the risk-panel
   classifier surfaces the banner — see the test fixture in
   `workbench/backend/tests/unit/test_risk_panel.py::test_risk_panel_red_state_includes_defensive_ticket`.

Until the PNGs land, the workbench README (`workbench/README.md`) points
at this checklist so reviewers know where the gallery lives.
