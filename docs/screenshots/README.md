# Workbench screenshots — B022 F013 capture checklist

This directory holds PNG screenshots of the seven research pages
delivered in B022. The acceptance text asks for one PNG per page, ≤300 KB
each, named consistently.

## What to capture

| Filename | Page | What it should show |
|---|---|---|
| `01-home.png` | `/` | 4 dashboard cards (NAV / DD / Kill-switch / Days-to-Rebalance) + Recent reports list + Action items panel. |
| `02-strategies.png` | `/strategies` | Sleeve DataTable with all 4 rows + per-strategy detail panel (config Card + Equity / Drawdown / Heatmap stacked + Spec/Code/Sweep buttons). |
| `03-backtest.png` | `/backtest` | ResizablePanel split: selector pane left + result stack right (Metrics card + Equity curve + Drawdown + Trades). After clicking Run. |
| `04-reports.png` | `/reports` | List of reports + click into one (e.g. B019 retune) showing the sweep matrix rendered as a sortable AG Grid (≥10-row swap). |
| `05-recommendations.png` | `/recommendations` | Disclaimer Card + AllocationPie + AllocationBar + positions DataTable + gate panel + Export Markdown Ticket button (the post-export "Wrote …" line if available). |
| `06-snapshots.png` | `/snapshots` | DataTable of snapshots + Refresh modal mid-stream (showing at least one stage event). |
| `07-backlog.png` | `/backlog` | DataTable filtered to `high` priority + the Add-entry Dialog open. |

## Generator gap

Screenshot capture requires a browser session and is not something the
generator agent can produce automatically. Two practical paths:

1. **Operator capture (recommended).** Sign into `https://trade.guangai.ai`
   with the allowed Google account, walk the seven pages, and save each
   screenshot at 1440×900 (or device-default) into this directory. Use
   `pngquant --quality=70-90` if any file lands above the 300 KB budget.
2. **Codex L2 capture.** During F014 verification on the real VM, the
   evaluator can save Playwright trace screenshots from the authed
   project's runs (Playwright stores them under
   `workbench/frontend/test-results/`) and curate the seven that match
   the checklist above.

Until the PNGs land, the workbench README (`workbench/README.md`) points
at this checklist so reviewers know where the gallery lives.
